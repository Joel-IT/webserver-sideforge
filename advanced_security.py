import os
import sys
import logging
import time
import json
import threading
from typing import Dict, List, Any

# Optional dependencies with graceful fallback
try:
    import psutil
except ImportError:
    psutil = None

try:
    import pyinotify
except ImportError:
    pyinotify = None

try:
    import scapy.all as scapy
except ImportError:
    scapy = None

try:
    import fail2ban
except ImportError:
    fail2ban = None

class AdvancedSecurityManager:
    def __init__(self, config_path: str = 'advanced_security_config.json'):
        # Configure logging first
        self._setup_logging()
        
        # Load configuration
        self.config = self._load_security_config(config_path)
        
        # Check and warn about missing dependencies
        self._check_dependencies()
        
        # Initialize security features
        self.attack_detection_active = False
        self.malware_signatures = self._load_malware_signatures()
        self.ddos_protection_active = False

    def _setup_logging(self):
        """Configure secure, comprehensive logging."""
        log_dir = os.path.join(os.getcwd(), 'security_logs')
        os.makedirs(log_dir, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, 'advanced_security.log'), mode='a'),
                logging.StreamHandler(sys.stdout)
            ]
        )

    def _check_dependencies(self):
        """Check and log warnings about missing dependencies."""
        missing_deps = []
        
        if psutil is None:
            missing_deps.append("psutil")
            logging.warning("psutil not installed. Some system monitoring features will be disabled.")
        
        if pyinotify is None:
            missing_deps.append("pyinotify")
            logging.warning("pyinotify not installed. File system monitoring will be disabled.")
        
        if scapy is None:
            missing_deps.append("scapy")
            logging.warning("scapy not installed. Network scanning features will be disabled.")
        
        if fail2ban is None:
            missing_deps.append("fail2ban")
            logging.warning("fail2ban not installed. Brute force protection features will be disabled.")
        
        if missing_deps:
            logging.error(f"Missing dependencies: {', '.join(missing_deps)}")
            logging.error("Please install these dependencies to enable full security features.")

    def _load_security_config(self, config_path: str) -> Dict[str, Any]:
        """Load advanced security configuration."""
        default_config = {
            'max_concurrent_connections': 500,
            'connection_rate_limit': 100,
            'block_countries': [],
            'whitelist_ips': [],
            'blacklist_ips': [],
            'malware_scan_interval': 3600,
            'ddos_threshold': {
                'syn_flood': 100,
                'icmp_flood': 50,
                'udp_flood': 75
            }
        }
        
        try:
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        except FileNotFoundError:
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=4)
        
        return default_config

    def _load_malware_signatures(self) -> List[str]:
        """Load known malware signatures."""
        signatures_path = os.path.join(os.getcwd(), 'malware_signatures.txt')
        try:
            with open(signatures_path, 'r') as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            default_signatures = [
                '<?php eval(',  # PHP remote code execution
                'base64_decode',  # Potential malware obfuscation
                'system(',  # Command execution
                'exec(',  # Shell execution
                'shell_exec(',  # Shell command execution
            ]
            with open(signatures_path, 'w') as f:
                f.write('\n'.join(default_signatures))
            return default_signatures

    def detect_syn_flood(self) -> bool:
        """Detect SYN flood attack."""
        if psutil is None:
            logging.warning("Cannot detect SYN flood: psutil not installed")
            return False
        
        try:
            syn_count = sum(1 for conn in psutil.net_connections() if conn.status == 'SYN_SENT')
            return syn_count > self.config['ddos_threshold']['syn_flood']
        except Exception as e:
            logging.error(f"Error detecting SYN flood: {e}")
            return False

    def monitor_file_system(self):
        """Monitor file system for suspicious changes."""
        if pyinotify is None:
            logging.warning("Cannot monitor file system: pyinotify not installed")
            return

        class FileChangeHandler(pyinotify.ProcessEvent):
            def process_IN_CREATE(self, event):
                logging.info(f"File created: {event.pathname}")
                self.scan_for_malware(event.pathname)
            
            def process_IN_MODIFY(self, event):
                logging.info(f"File modified: {event.pathname}")
                self.scan_for_malware(event.pathname)

        wm = pyinotify.WatchManager()
        mask = pyinotify.IN_CREATE | pyinotify.IN_MODIFY
        handler = FileChangeHandler()
        notifier = pyinotify.Notifier(wm, handler)
        wdd = wm.add_watch('/var/www/html', mask, rec=True)

        threading.Thread(target=notifier.loop, daemon=True).start()

    def scan_for_malware(self, file_path: str) -> bool:
        """Scan a file for potential malware using signature detection."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                for signature in self.malware_signatures:
                    if signature in content:
                        logging.critical(f"Malware signature detected in {file_path}: {signature}")
                        return True
            return False
        except Exception as e:
            logging.error(f"Error scanning {file_path}: {e}")
            return False

    def start_ddos_protection(self):
        """Start DDoS protection mechanisms."""
        if not self.ddos_protection_active:
            self.ddos_protection_active = True
            threading.Thread(target=self._ddos_monitor, daemon=True).start()
            logging.info("DDoS protection started")

    def _ddos_monitor(self):
        """Continuously monitor for potential DDoS attacks."""
        while self.ddos_protection_active:
            if self.detect_syn_flood():
                logging.critical("Potential SYN Flood Attack Detected!")
            time.sleep(60)  # Check every minute

def initialize_advanced_security():
    """Initialize advanced security measures."""
    security_manager = AdvancedSecurityManager()
    
    # Start file system monitoring
    security_manager.monitor_file_system()
    
    # Start DDoS protection
    security_manager.start_ddos_protection()
    
    return security_manager

if __name__ == "__main__":
    advanced_security = initialize_advanced_security()
    logging.info("Advanced Security System Initialized")
