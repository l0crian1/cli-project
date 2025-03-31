# CLI Configuration Manager

A Python-based CLI tool for managing network configurations with features like command completion, error handling, and configuration management.

## Features

- Command-line interface with auto-completion
- Configuration management (running and candidate configs)
- Static route configuration
- Interface management
- Error handling and validation
- FRR configuration rendering

## Installation

1. Clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/CLI.git
cd CLI
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the CLI tool:
```bash
python configCli.py
```

### Basic Commands

- `show running` - Display running configuration
- `show candidate` - Display candidate configuration
- `set protocols static route <prefix> next-hop <address>` - Set a static route
- `delete protocols static route <prefix>` - Delete a static route
- `commit` - Apply candidate configuration
- `discard` - Discard candidate configuration

## Project Structure

```
.
├── configCli.py          # Main CLI application
├── cli_common.py         # Common CLI utilities
├── validators.py         # Input validation functions
├── suggestors.py        # Interface suggestion functions
├── renderers/           # Configuration renderers
│   ├── static.py       # Static route renderer
│   └── frr.conf.j2     # FRR configuration template
├── config.json          # Command structure configuration
└── commands.json        # Command definitions
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 