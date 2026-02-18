# Contributing to AgentEvolution

First off, thank you for considering contributing to AgentEvolution! 🎉

## How to Contribute

### Reporting Bugs
- Use the GitHub Issues tab
- Include steps to reproduce
- Include your Python version and OS

### Suggesting Features
- Open a Feature Request issue
- Describe the use case
- Explain why it would benefit the community

### Submitting Code

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run tests: `pytest tests/ -v`
5. Commit: `git commit -m 'Add amazing feature'`
6. Push: `git push origin feature/amazing-feature`
7. Open a Pull Request

### Development Setup

```bash
git clone https://github.com/YOUR_USERNAME/agentevolution.git
cd agentevolution
pip install -e ".[dev]"
pytest tests/ -v
```

### Code Style

- We use `ruff` for linting
- Type hints are required for all public functions
- Docstrings are required for all public classes and functions

## Priority Areas

We're actively looking for help with:

1. **Docker Sandbox** — Replace subprocess isolation with Docker containers
2. **HTTP Transport** — Add SSE/WebSocket MCP transport alongside stdio
3. **TypeScript SDK** — Client SDK for JS/TS agents
4. **Better Discovery** — Intent decomposition and multi-hop reasoning
5. **Test Suite** — More edge cases and integration tests
6. **Documentation** — Tutorials, guides, and API docs

## Code of Conduct

Be kind, be constructive, be inclusive. We're all here to build something amazing.
