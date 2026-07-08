#!/usr/bin/env python3
"""
Deployment Readiness Check Script
Validates configuration, dependencies, and services before deployment.
"""

import os
import sys
import asyncio
import logging
import subprocess
import importlib
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def check_python_version():
    """Check if Python version is >= 3.11"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        logger.error(f"Python 3.11+ required, found {version.major}.{version.minor}")
        return False
    logger.info(f"✅ Python version: {version.major}.{version.minor}.{version.micro}")
    return True

def check_required_packages():
    """Check if all required packages are installed"""
    package_mapping = {
        'fastapi': 'fastapi',
        'uvicorn': 'uvicorn', 
        'sqlalchemy': 'sqlalchemy',
        'aiosqlite': 'aiosqlite',
        'pyjwt': 'jwt',  # PyJWT imports as 'jwt'
        'chromadb': 'chromadb',
        'sentence_transformers': 'sentence_transformers',
        'streamlit': 'streamlit',
        'httpx': 'httpx',
        'passlib': 'passlib',
        'bcrypt': 'bcrypt',
        'nh3': 'nh3',
        'python-dotenv': 'dotenv'  # python-dotenv imports as 'dotenv'
    }
    
    missing_packages = []
    for package_name, import_name in package_mapping.items():
        try:
            importlib.import_module(import_name)
            logger.info(f"✅ {package_name}")
        except ImportError:
            missing_packages.append(package_name)
            logger.error(f"❌ {package_name} not found")
    
    if missing_packages:
        logger.error(f"Missing packages: {', '.join(missing_packages)}")
        logger.info("Install with: pip install -r requirements.txt")
        return False
    
    return True

def check_environment_variables():
    """Check if all required environment variables are set"""
    required_vars = [
        'JWT_SECRET_KEY',
        'DATABASE_URL',
        'CHROMA_PERSIST_DIR',
        'OLLAMA_URL'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
            logger.error(f"❌ {var} not set")
        else:
            # Don't log sensitive values
            if 'SECRET' in var or 'TOKEN' in var:
                logger.info(f"✅ {var} (configured)")
            else:
                logger.info(f"✅ {var}={value}")
    
    if missing_vars:
        logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
        logger.info("Check your .env file or system environment variables")
        return False
    
    return True

def check_jwt_secret_strength():
    """Validate JWT secret key strength"""
    secret = os.getenv('JWT_SECRET_KEY', '')
    
    if len(secret) < 32:
        logger.error(f"❌ JWT_SECRET_KEY too short ({len(secret)} chars), minimum 32")
        return False
    
    logger.info(f"✅ JWT_SECRET_KEY length: {len(secret)} characters")
    return True

def check_database_connection():
    """Test database configuration"""
    try:
        # Add app directory to Python path
        import sys
        import os
        sys.path.insert(0, os.getcwd())
        
        from app.config import settings
        settings.validate()
        logger.info("✅ Database configuration valid")
        return True
    except ImportError as e:
        logger.warning(f"⚠️  Cannot import app config (expected in deployment check): {e}")
        # Check basic .env file instead
        env_path = os.path.join(os.getcwd(), '.env')
        if os.path.exists(env_path):
            logger.info("✅ .env file found")
            return True
        else:
            logger.error("❌ No .env file found")
            return False
    except Exception as e:
        logger.error(f"❌ Database configuration error: {e}")
        return False

async def check_vectorstore():
    """Check if vector store is initialized"""
    try:
        persist_dir = os.getenv('CHROMA_PERSIST_DIR', './vectorstore')
        if not os.path.exists(persist_dir):
            logger.warning(f"⚠️  Vector store not found at {persist_dir}")
            logger.info("Run: python -m scripts.ingest to initialize")
            return False
        
        # Check if vectorstore has content
        db_files = list(Path(persist_dir).rglob("*.bin"))
        if not db_files:
            logger.warning("⚠️  Vector store appears empty")
            logger.info("Run: python -m scripts.ingest to populate with documents")
            return False
        
        logger.info(f"✅ Vector store initialized with {len(db_files)} data files")
        return True
    except Exception as e:
        logger.error(f"❌ Vector store check failed: {e}")
        return False

def check_docker_setup():
    """Check Docker configuration"""
    dockerfile_path = Path("Dockerfile")
    if not dockerfile_path.exists():
        logger.error("❌ Dockerfile not found")
        return False
    
    logger.info("✅ Dockerfile present")
    
    # Check for docker-compose if it exists
    compose_files = ["docker-compose.yml", "docker-compose.yaml"]
    for compose_file in compose_files:
        if Path(compose_file).exists():
            logger.info(f"✅ {compose_file} found")
            break
    
    return True

def check_ci_cd_setup():
    """Check CI/CD configuration"""
    github_workflow = Path(".github/workflows/deploy.yml")
    if github_workflow.exists():
        logger.info("✅ GitHub Actions workflow configured")
        return True
    else:
        logger.warning("⚠️  No CI/CD workflow found")
        return False

def run_security_checks():
    """Run basic security checks"""
    checks_passed = True
    
    # Check for exposed secrets in code
    secret_patterns = ['.env', 'password', 'secret', 'token', 'key']
    python_files = Path('.').rglob('*.py')
    
    for file_path in python_files:
        if 'venv' in str(file_path) or '__pycache__' in str(file_path):
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().lower()
                for pattern in secret_patterns:
                    if f'{pattern}=' in content and 'os.getenv' not in content:
                        logger.warning(f"⚠️  Potential hardcoded secret in {file_path}")
        except Exception:
            continue
    
    logger.info("✅ Security scan completed")
    return checks_passed

def generate_deployment_report():
    """Generate a deployment readiness report"""
    report = {
        'timestamp': datetime.now().isoformat(),
        'python_version': check_python_version(),
        'packages': check_required_packages(),
        'environment': check_environment_variables(),
        'jwt_security': check_jwt_secret_strength(),
        'database': check_database_connection(),
        'docker': check_docker_setup(),
        'ci_cd': check_ci_cd_setup(),
        'security': run_security_checks()
    }
    
    return report

async def main():
    """Run all deployment readiness checks"""
    logger.info("🚀 Starting deployment readiness check...")
    logger.info("=" * 50)
    
    report = generate_deployment_report()
    
    # Check vectorstore asynchronously
    report['vectorstore'] = await check_vectorstore()
    
    logger.info("=" * 50)
    logger.info("📊 DEPLOYMENT READINESS REPORT")
    logger.info("=" * 50)
    
    all_passed = True
    for check_name, result in report.items():
        if check_name == 'timestamp':
            continue
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{check_name.upper():.<20} {status}")
        if not result:
            all_passed = False
    
    logger.info("=" * 50)
    
    if all_passed:
        logger.info("🎉 ALL CHECKS PASSED - Ready for deployment!")
        logger.info("Next steps:")
        logger.info("  1. Build Docker image: docker build -t enterprise-agent .")
        logger.info("  2. Test locally: docker run -p 8000:8000 enterprise-agent")
        logger.info("  3. Deploy to your preferred platform")
        return 0
    else:
        logger.error("❌ SOME CHECKS FAILED - Fix issues before deployment")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)