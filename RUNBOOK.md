# RescueNet AI - Production Runbook

**Version:** 1.0  
**Date:** March 2026  
**Purpose:** Operational guide for running RescueNet AI in production environments

---

## 📋 Table of Contents
1. [System Overview](#system-overview)
2. [Installation & Setup](#installation--setup)
3. [Runtime Modes](#runtime-modes)
4. [Configuration Management](#configuration-management)
5. [Monitoring & Logging](#monitoring--logging)
6. [Troubleshooting](#troubleshooting)
7. [Performance Tuning](#performance-tuning)
8. [Security Considerations](#security-considerations)
9. [Backup & Recovery](#backup--recovery)

---

## 🏗️ System Overview

RescueNet AI is an autonomous disaster response system that coordinates fleets of drones for search, rescue, and supply delivery operations.

### Core Components
- **Main Simulation Engine** (`main.py`): Core simulation loop
- **Environment Factory** (`simulation/factory.py`): Creates demo or sim environments
- **AI Agents** (`agents/`): State awareness, triage, coordination
- **Dashboard** (`dashboard/app.py`): Web-based monitoring interface
- **Configuration System** (`config/`): Multi-source configuration management

### Data Flow
```
Environment (Demo/Sim) → Fleet State → AI Agents → Mission Assignments → Environment
```

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.9+
- Virtual environment (recommended)
- Network access (for sim mode)

### Step-by-Step Setup
```bash
# 1. Clone repository
git clone <repository-url>
cd rescuenet-ai

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify installation
python main.py --mode demo --ticks 2
```

### AirSim Setup (Optional, for Sim Mode)
```bash
# Install AirSim Python client
pip install airsim

# Start AirSim simulator
# (Follow AirSim documentation for simulator setup)
```

---

## ⚙️ Runtime Modes

### 1. Demo Mode (Default)
**Purpose:** Development, testing, and CI/CD
```bash
# Basic usage
python main.py --mode demo --ticks 10

# With verbose logging
python main.py --mode demo --ticks 10 --verbose

# Custom configuration
export RESCUENET_MOCK_SEED=123
export RESCUENET_MOCK_NUM_DRONES=5
python main.py --mode demo
```

### 2. Sim Mode (AirSim Integration)
**Purpose:** Realistic simulation with AirSim
```bash
# Basic usage (requires AirSim running)
python main.py --mode sim --ticks 5

# Custom AirSim connection
export RESCUENET_AIRSIM_HOST=192.168.1.100
export RESCUENET_AIRSIM_PORT=41451
python main.py --mode sim

# With fallback to demo mode if AirSim unavailable
# (System will automatically suggest demo mode on connection failure)
```

### 3. Dashboard Mode
**Purpose:** Real-time monitoring and control
```bash
# Start dashboard
streamlit run dashboard/app.py

# Access at: http://localhost:8501

# Custom port
streamlit run dashboard/app.py --server.port 8502
```

---

## 🔧 Configuration Management

### Configuration Sources (Priority Order)
1. **Command-line arguments** (highest priority)
2. **Environment variables**
3. **Config file** (`config.json`)
4. **Default values**

### Configuration File (`config.json`)
```json
{
    "mode": "demo",
    "mock_seed": 42,
    "mock_num_drones": 3,
    "mock_num_victims": 4,
    "airsim_host": "localhost",
    "airsim_port": 41451,
    "log_level": "INFO"
}
```

### Environment Variables Reference
| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `RESCUENET_MODE` | Runtime mode | `demo` | `export RESCUENET_MODE=sim` |
| `RESCUENET_MOCK_SEED` | Demo random seed | `42` | `export RESCUENET_MOCK_SEED=123` |
| `RESCUENET_MOCK_NUM_DRONES` | Demo drone count | `3` | `export RESCUENET_MOCK_NUM_DRONES=5` |
| `RESCUENET_MOCK_NUM_VICTIMS` | Demo victim count | `4` | `export RESCUENET_MOCK_NUM_VICTIMS=8` |
| `RESCUENET_AIRSIM_HOST` | AirSim host | `localhost` | `export RESCUENET_AIRSIM_HOST=10.0.0.5` |
| `RESCUENET_AIRSIM_PORT` | AirSim port | `41451` | `export RESCUENET_AIRSIM_PORT=41452` |
| `RESCUENET_LOG_LEVEL` | Logging level | `INFO` | `export RESCUENET_LOG_LEVEL=DEBUG` |

---

## 📊 Monitoring & Logging

### Logging Levels
- **DEBUG**: Detailed information for debugging
- **INFO**: General operational information
- **WARNING**: Potential issues that don't stop execution
- **ERROR**: Serious problems that may affect functionality
- **CRITICAL**: Fatal errors that stop execution

### Log Configuration
```python
# Programmatic configuration
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
```

### Key Metrics to Monitor
1. **Fleet Readiness**: Percentage of operational drones
2. **Mission Completion Rate**: Successful missions vs total
3. **Triage Efficiency**: Time from detection to assignment
4. **System Latency**: Tick processing time
5. **Error Rate**: Failed operations per tick

### Dashboard Metrics
- Real-time drone status
- Mission progress tracking
- Triage priority queue
- Fleet readiness percentage
- System uptime and performance

---

## 🔍 Troubleshooting

### Common Issues and Solutions

#### Issue: Demo Mode Fails to Start
**Symptoms:** Python errors or crashes on startup
**Solutions:**
```bash
# 1. Check Python version
python --version  # Should be 3.9+

# 2. Check dependencies
pip list | grep -E "(streamlit|numpy|pandas)"

# 3. Enable debug logging
python main.py --mode demo --verbose

# 4. Reset configuration
rm config.json  # Remove custom config
python main.py --mode demo
```

#### Issue: Sim Mode Connection Failed
**Symptoms:** "Failed to connect to AirSim" error
**Solutions:**
```bash
# 1. Verify AirSim is running
# Check AirSim simulator UI

# 2. Test network connectivity
ping <airsim-host>
telnet <airsim-host> <airsim-port>

# 3. Use demo mode as fallback
python main.py --mode demo

# 4. Check AirSim Python client
python -c "import airsim; print(airsim.__version__)"
```

#### Issue: Dashboard Won't Start
**Symptoms:** Streamlit errors or port conflicts
**Solutions:**
```bash
# 1. Check Streamlit installation
pip show streamlit

# 2. Try different port
streamlit run dashboard/app.py --server.port 8502

# 3. Check for existing processes
lsof -i :8501  # Linux/Mac
# netstat -ano | findstr :8501  # Windows

# 4. Update Streamlit
pip install --upgrade streamlit
```

#### Issue: Performance Degradation
**Symptoms:** Slow tick processing, high memory usage
**Solutions:**
```bash
# 1. Reduce tick count
python main.py --mode demo --ticks 3

# 2. Reduce fleet size
export RESCUENET_MOCK_NUM_DRONES=2
export RESCUENET_MOCK_NUM_VICTIMS=3

# 3. Monitor memory usage
# Use system monitoring tools

# 4. Check for memory leaks
# Run with limited ticks and monitor memory
```

### Error Messages Reference

| Error Message | Likely Cause | Solution |
|---------------|--------------|----------|
| `Failed to create environment` | Missing dependencies or configuration | Check Python imports, verify config |
| `AirSim connection failed` | AirSim not running or network issue | Start AirSim, check network |
| `ModuleNotFoundError` | Missing Python package | `pip install -r requirements.txt` |
| `Port already in use` | Another process using the port | Use different port or kill existing process |
| `Invalid configuration` | Malformed config.json | Delete config.json or fix JSON syntax |

---

## ⚡ Performance Tuning

### For Development/Testing
```bash
# Minimal configuration for fast testing
export RESCUENET_MOCK_NUM_DRONES=2
export RESCUENET_MOCK_NUM_VICTIMS=3
python main.py --mode demo --ticks 5
```

### For Production Simulation
```bash
# Realistic configuration
export RESCUENET_MOCK_NUM_DRONES=5
export RESCUENET_MOCK_NUM_VICTIMS=10
export RESCUENET_LOG_LEVEL=WARNING  # Reduce logging overhead
python main.py --mode demo --ticks 100
```

### Memory Optimization
- Reduce number of drones/victims for large simulations
- Use `--ticks` to limit simulation duration
- Monitor memory usage with system tools
- Consider periodic state cleanup for long runs

### CPU Optimization
- Run with `--verbose` only when debugging
- Set `RESCUENET_LOG_LEVEL=WARNING` for production
- Consider running dashboard on separate machine if needed

---

## 🔒 Security Considerations

### Network Security (Sim Mode)
- AirSim connections are unencrypted by default
- Consider VPN or secure network for production deployments
- Firewall rules to restrict access to AirSim port

### Configuration Security
- Avoid committing sensitive data to version control
- Use environment variables for production secrets
- Regular rotation of any API keys or credentials

### Access Control
- Dashboard should be behind authentication in production
- Limit network exposure of monitoring interfaces
- Regular security updates for dependencies

### Audit Logging
- All critical actions are logged
- Mission assignments and completions are tracked
- System errors and warnings are recorded
- Consider external log aggregation for production

---

## 💾 Backup & Recovery

### Configuration Backup
```bash
# Backup configuration
cp config.json config.json.backup

# Backup with timestamp
cp config.json config.json.$(date +%Y%m%d_%H%M%S).backup
```

### State Recovery
- System state is not persisted between runs
- Each simulation starts fresh
- Consider implementing state serialization for critical applications

### Disaster Recovery Steps
1. **Configuration Loss**: Restore from `config.json.backup`
2. **Code Corruption**: `git checkout` to restore from version control
3. **Dependency Issues**: `pip install -r requirements.txt`
4. **Data Loss**: Re-run simulation (state is ephemeral)

### Regular Maintenance
- Update dependencies: `pip install --upgrade -r requirements.txt`
- Clear Python cache: `find . -name "__pycache__" -type d -exec rm -rf {} +`
- Verify installation: `python main.py --mode demo --ticks 1`
- Check logs for errors: Review recent log files

---

## 📞 Support & Escalation

### First Line Support
- Check README.md for basic usage
- Review RUNBOOK.md for operational guidance
- Check logs for error messages

### Development Support
- Repository maintainers
- Check GitHub issues for known problems
- Review recent commits for changes

### Emergency Contacts
- System architect: @revailace
- Operations team: [Team contact information]

### Escalation Path
1. Check logs and error messages
2. Review configuration and environment
3. Test with minimal configuration
4. Contact development team
5. Consider rolling back to known good state

---

## 📈 Performance Benchmarks

### Expected Performance
- **Demo Mode**: 5-10 ticks/second (depending on configuration)
- **Sim Mode**: 2-5 ticks/second (network dependent)
- **Dashboard**: < 1 second refresh latency
- **Memory Usage**: 50-200 MB (scales with fleet size)

### Load Testing
```bash
# Test with increasing load
for drones in 2 4 8; do
  for victims in 4 8 16; do
    echo "Testing: $drones drones, $victims victims"
    export RESCUENET_MOCK_NUM_DRONES=$drones
    export RESCUENET_MOCK_NUM_VICTIMS=$victims
    time python main.py --mode demo --ticks 10 --verbose 2>&1 | tail -5
    echo "---"
  done
done
```

---

## 🎯 Best Practices

### Development
1. Use demo mode for testing and development
2. Commit `config.json` with safe defaults only
3. Use environment variables for machine-specific settings
4. Write tests for new agents and components

### Operations
1. Start with demo mode to verify system health
2. Use verbose logging only when debugging
3. Monitor system resources during long runs
4. Keep backups of critical configuration

### Deployment
1. Use virtual environments for isolation
2. Consider containerization for production
3. Implement health checks for long-running processes
4. Set up monitoring and alerting

---

**Last Updated:** March 2026  
**Maintainer:** RescueNet AI Operations Team