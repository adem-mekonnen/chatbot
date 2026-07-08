# Enterprise AI Agent

A production-ready enterprise AI assistant with secure authentication, RAG-based knowledge retrieval, and comprehensive audit logging.

## 🚀 Features

- **Secure Authentication**: JWT-based authentication with refresh token rotation (RTR)
- **Role-Based Access Control**: Admin and customer roles with different permissions
- **RAG Knowledge Base**: ChromaDB vector store for enterprise document retrieval  
- **Local LLM Integration**: Support for Ollama and HuggingFace models
- **Comprehensive Auditing**: All interactions logged with correlation IDs
- **Modern UI**: Responsive Streamlit interface with dark theme
- **Production Ready**: Docker containerization, CI/CD pipeline, health checks

## 📋 Requirements

- Python 3.11+
- Docker (optional, for containerized deployment)
- Ollama (for local LLM) or HuggingFace token

## 🛠️ Installation

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd enterprise_agent
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Initialize the database and vector store**
   ```bash
   python -m scripts.ingest
   ```

5. **Run the application**
   ```bash
   # Option 1: Embedded Streamlit (simplest)
   streamlit run app.py

   # Option 2: Separate FastAPI + Streamlit
   uvicorn app.main:app --host 0.0.0.0 --port 8000 &
   streamlit run ui/streamlit_app.py --server.port 8501
   ```

### Docker Deployment

1. **Check deployment readiness**
   ```bash
   python scripts/check_deployment.py
   ```

2. **Build and run with Docker Compose**
   ```bash
   # Create JWT secret
   mkdir -p secrets
   python -c "import secrets; print(secrets.token_urlsafe(48))" > secrets/jwt_secret.txt

   # Start all services
   docker-compose up -d
   
   # Or with UI
   docker-compose --profile ui up -d
   ```

3. **Access the application**
   - **API**: http://localhost:8000
   - **UI**: http://localhost:8501  
   - **Health**: http://localhost:8000/health

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JWT_SECRET_KEY` | JWT signing secret (required, 32+ chars) | - |
| `DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./enterprise_state.db` |
| `CHROMA_PERSIST_DIR` | Vector store directory | `./vectorstore` |
| `OLLAMA_URL` | Ollama service URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Default model name | `llama3.2:latest` |
| `HF_INFERENCE_TOKEN` | HuggingFace token (fallback) | - |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime | `30` |

### Default Users

The system initializes with demo users:

- **Admin**: `admin` / `admin123`
- **Customer**: `alice` / `alice123`
- **Customer**: `bob` / `bob123`

**⚠️ Change these credentials in production!**

## 📚 API Documentation

Once running, visit:
- **Interactive API Docs**: http://localhost:8000/docs
- **OpenAPI Schema**: http://localhost:8000/openapi.json

### Key Endpoints

- `POST /token` - Authenticate and get access token
- `POST /refresh` - Refresh access token  
- `POST /chat` - Send message to AI assistant
- `POST /logout` - Revoke refresh token
- `GET /health` - Health check

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Streamlit UI  │───▶│   FastAPI API   │───▶│     Ollama      │
│                 │    │                 │    │   (LLM Server)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                               │
                               ▼
                    ┌─────────────────┐    ┌─────────────────┐
                    │   PostgreSQL/   │    │    ChromaDB     │
                    │     SQLite      │    │ (Vector Store)  │
                    │   (User Data)   │    │  (Documents)    │
                    └─────────────────┘    └─────────────────┘
```

### Components

- **Frontend**: Streamlit with modern responsive UI
- **Backend**: FastAPI with async SQLAlchemy  
- **Authentication**: JWT with refresh token rotation
- **Vector Store**: ChromaDB for document embeddings
- **LLM**: Ollama (local) or HuggingFace (cloud fallback)
- **Database**: SQLite (dev) or PostgreSQL (production)

## 🛡️ Security Features

- **JWT Authentication**: Secure token-based auth with rotation
- **Input Sanitization**: HTML/XSS protection with nh3
- **RBAC Authorization**: Role-based permissions
- **Rate Limiting**: Configurable per-IP request limits  
- **Audit Logging**: Comprehensive activity logs
- **Secrets Management**: Docker BuildKit secrets support

## 📖 Usage Examples

### Chat with the Assistant

```python
import httpx

# Login
response = httpx.post("http://localhost:8000/token", json={
    "username": "alice", 
    "password": "alice123"
})
token = response.json()["access_token"]

# Chat
response = httpx.post("http://localhost:8000/chat", 
    headers={"Authorization": f"Bearer {token}"},
    json={
        "message": "What are the company vacation policies?",
        "session_id": "session-123"
    }
)
print(response.json()["response"])
```

### Account Balance Query

```python
# Admin can check any balance
response = httpx.post("http://localhost:8000/chat",
    headers={"Authorization": f"Bearer {admin_token}"},
    json={"message": "balance of alice"}
)

# Customers can only check their own
response = httpx.post("http://localhost:8000/chat", 
    headers={"Authorization": f"Bearer {alice_token}"},
    json={"message": "balance of alice"}  # ✅ Allowed
)

response = httpx.post("http://localhost:8000/chat",
    headers={"Authorization": f"Bearer {alice_token}"}, 
    json={"message": "balance of bob"}    # ❌ Forbidden
)
```

## 🧪 Testing

Run the test suite:

```bash
# All tests
pytest

# Specific test categories
pytest tests/test_security.py -v
pytest tests/test_agent.py -k "balance" -v

# With coverage
pytest --cov=app tests/
```

## 🚀 Production Deployment

### 1. Deployment Checklist

```bash
# Run deployment readiness check
python scripts/check_deployment.py

# Build production image
bash scripts/production_deploy.sh
```

### 2. Environment Setup

- Set strong JWT secret (48+ characters)
- Configure PostgreSQL for production
- Set up monitoring and log aggregation
- Configure reverse proxy (nginx/Cloudflare)
- Set up SSL/TLS certificates

### 3. Monitoring

The application provides:
- Health check endpoint: `/health`
- Metrics in logs (JSON format)
- Structured audit trails
- Performance timing information

### 4. Scaling Considerations

- **Stateless**: Can run multiple instances
- **Database**: Use PostgreSQL with connection pooling  
- **LLM**: Scale Ollama instances or use cloud APIs
- **Vector Store**: ChromaDB supports clustering

## 🔧 Development

### Project Structure

```
enterprise_agent/
├── app/                    # Main application
│   ├── main.py            # FastAPI application  
│   ├── chatbot.py         # AI agent logic
│   ├── security.py        # Authentication & auth
│   ├── database.py        # Database models & logic
│   ├── config.py          # Configuration management
│   ├── llm/               # LLM client interfaces
│   ├── rag/               # RAG retriever logic
│   └── tools/             # Tool routing system
├── ui/                    # Streamlit interface
├── tests/                 # Test suite
├── scripts/               # Deployment & utility scripts
├── data/knowledge_base/   # Enterprise documents  
├── .github/workflows/     # CI/CD pipelines
├── Dockerfile             # Production container
├── docker-compose.yml     # Multi-service deployment
└── requirements.txt       # Python dependencies
```

### Adding New Features

1. **New Knowledge Documents**: Add to `data/knowledge_base/` and run `python -m scripts.ingest`

2. **New Tools**: Create in `app/tools/` and register in `router.py`

3. **UI Enhancements**: Modify `ui/streamlit_app.py` or `app.py`

4. **API Extensions**: Add endpoints in `app/main.py`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Style

- **Python**: Follow PEP 8, use type hints
- **Tests**: Maintain 90%+ coverage
- **Commits**: Use conventional commit messages
- **Documentation**: Update README for user-facing changes

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/your-org/enterprise-agent/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/enterprise-agent/discussions)
- **Documentation**: See `/docs` directory
- **Email**: support@yourcompany.com

## 🔮 Roadmap

- [ ] Multi-tenant support
- [ ] Advanced analytics dashboard
- [ ] Integration with external APIs
- [ ] Mobile-responsive UI improvements  
- [ ] Advanced role management
- [ ] Real-time collaboration features
- [ ] Enhanced security scanning
- [ ] Performance optimization

---

**Built with ❤️ for enterprise-grade AI applications**