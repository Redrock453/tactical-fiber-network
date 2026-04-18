# Contributing to TFN — Project SpiderLink

Thank you for your interest in contributing!

## How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Commit your changes (`git commit -m "feat: description"`)
4. Push to your fork (`git push origin feat/my-feature`)
5. Open a Pull Request

## Commit Convention

```
feat: new feature
fix: bug fix
docs: documentation
sim: simulation/scenario
calc: calculator update
test: tests
infra: CI/CD, Docker, configs
```

## Code Style

- Python 3.11+
- No external dependencies without justification
- Type hints where helpful
- Docstrings for public functions and classes
- Ukrainian/English bilingual docs are welcome

## Testing

```bash
python -m pytest tests/ -v
```

## Security

- Never commit tokens, keys, or credentials
- Use `.env` for secrets (included in `.gitignore`)
- Report security issues via GitHub Issues

## Areas of Contribution

- **Simulation:** New scenarios, targets, physics models
- **DAS:** New signature profiles, ML classification
- **RF-Opto:** Detection models, sensitivity analysis
- **Calculator:** New tools, optimizations
- **Documentation:** Translations, field guides, diagrams
- **Hardware:** BOM updates, new equipment reviews
- **Web Dashboard:** Visualization improvements

## License

By contributing, you agree that your work will be licensed under MIT.
