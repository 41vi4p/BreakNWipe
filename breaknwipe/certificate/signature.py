"""
Digital Signature Module

Handles cryptographic signing and verification of wipe certificates.
"""

import os
import time
import json
import logging
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from cryptography import x509
from cryptography.x509.oid import NameOID
import datetime

logger = logging.getLogger(__name__)


class DigitalSigner:
    """Handles digital signing of wipe certificates."""

    def __init__(self, key_size: int = 2048):
        """
        Initialize digital signer.

        Args:
            key_size: RSA key size in bits (default 2048)
        """
        self.key_size = key_size
        self.private_key = None
        self.public_key = None
        self.certificate = None

    def generate_key_pair(self) -> Tuple[bytes, bytes]:
        """
        Generate RSA key pair.

        Returns:
            Tuple of (private_key_pem, public_key_pem)
        """
        logger.info(f"Generating {self.key_size}-bit RSA key pair")

        # Generate private key
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=self.key_size,
            backend=default_backend()
        )

        # Get public key
        self.public_key = self.private_key.public_key()

        # Serialize keys to PEM format
        private_pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        public_pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        return private_pem, public_pem

    def load_key_pair(self, private_key_path: str, public_key_path: Optional[str] = None):
        """
        Load existing key pair from files.

        Args:
            private_key_path: Path to private key file
            public_key_path: Path to public key file (optional)
        """
        try:
            # Load private key
            with open(private_key_path, 'rb') as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                    backend=default_backend()
                )

            # Get public key from private key
            self.public_key = self.private_key.public_key()

            logger.info(f"Loaded key pair from {private_key_path}")

        except Exception as e:
            logger.error(f"Failed to load key pair: {e}")
            raise

    def create_self_signed_certificate(self, subject_name: str = "BreakNWipe Certificate Authority") -> bytes:
        """
        Create a self-signed certificate.

        Args:
            subject_name: Subject name for the certificate

        Returns:
            Certificate in PEM format
        """
        if not self.private_key:
            raise ValueError("Private key not loaded or generated")

        # Create certificate subject
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "India"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Mumbai"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "BreakNWipe"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Data Sanitization"),
            x509.NameAttribute(NameOID.COMMON_NAME, subject_name),
        ])

        # Create certificate
        cert_builder = x509.CertificateBuilder()
        cert_builder = cert_builder.subject_name(subject)
        cert_builder = cert_builder.issuer_name(issuer)
        cert_builder = cert_builder.public_key(self.public_key)
        cert_builder = cert_builder.serial_number(x509.random_serial_number())

        # Set validity period (10 years)
        cert_builder = cert_builder.not_valid_before(datetime.datetime.utcnow())
        cert_builder = cert_builder.not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=3650)
        )

        # Add extensions
        cert_builder = cert_builder.add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.DNSName("breaknwipe.local"),
            ]),
            critical=False,
        )

        cert_builder = cert_builder.add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )

        cert_builder = cert_builder.add_extension(
            x509.KeyUsage(
                key_cert_sign=True,
                crl_sign=True,
                digital_signature=True,
                key_encipherment=False,
                key_agreement=False,
                data_encipherment=False,
                content_commitment=False,
                encipher_only=False,
                decipher_only=False
            ),
            critical=True,
        )

        # Sign certificate
        self.certificate = cert_builder.sign(self.private_key, hashes.SHA256(), default_backend())

        # Return PEM format
        return self.certificate.public_bytes(serialization.Encoding.PEM)

    def sign_data(self, data: str) -> str:
        """
        Sign data with private key.

        Args:
            data: Data to sign (string)

        Returns:
            Base64-encoded signature
        """
        if not self.private_key:
            raise ValueError("Private key not loaded")

        try:
            # Convert data to bytes
            data_bytes = data.encode('utf-8')

            # Sign data
            signature = self.private_key.sign(
                data_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )

            # Return base64-encoded signature
            import base64
            return base64.b64encode(signature).decode('utf-8')

        except Exception as e:
            logger.error(f"Failed to sign data: {e}")
            raise

    def verify_signature(self, data: str, signature: str, public_key_pem: Optional[bytes] = None) -> bool:
        """
        Verify signature against data.

        Args:
            data: Original data
            signature: Base64-encoded signature
            public_key_pem: Public key in PEM format (optional, uses loaded key if None)

        Returns:
            True if signature is valid
        """
        try:
            import base64

            # Get public key
            if public_key_pem:
                public_key = serialization.load_pem_public_key(
                    public_key_pem,
                    backend=default_backend()
                )
            elif self.public_key:
                public_key = self.public_key
            else:
                raise ValueError("No public key available for verification")

            # Decode signature
            signature_bytes = base64.b64decode(signature.encode('utf-8'))
            data_bytes = data.encode('utf-8')

            # Verify signature
            public_key.verify(
                signature_bytes,
                data_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )

            return True

        except Exception as e:
            logger.debug(f"Signature verification failed: {e}")
            return False

    def create_timestamped_signature(self, data: str) -> Dict[str, Any]:
        """
        Create a timestamped signature.

        Args:
            data: Data to sign

        Returns:
            Dictionary with signature and timestamp information
        """
        timestamp = time.time()
        timestamp_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(timestamp))

        # Create signature payload including timestamp
        signature_payload = {
            'data': data,
            'timestamp': timestamp,
            'timestamp_iso': timestamp_iso,
            'signer': 'BreakNWipe Digital Signer',
            'algorithm': 'RSA-PSS-SHA256'
        }

        payload_string = json.dumps(signature_payload, sort_keys=True)
        signature = self.sign_data(payload_string)

        return {
            'signature': signature,
            'timestamp': timestamp,
            'timestamp_iso': timestamp_iso,
            'algorithm': 'RSA-PSS-SHA256',
            'payload_hash': self._calculate_hash(payload_string)
        }

    def save_keys(self, directory: str, prefix: str = "breaknwipe") -> Dict[str, str]:
        """
        Save keys to files.

        Args:
            directory: Directory to save keys
            prefix: Filename prefix

        Returns:
            Dictionary with file paths
        """
        os.makedirs(directory, exist_ok=True)

        files = {}

        if self.private_key:
            private_key_path = os.path.join(directory, f"{prefix}_private.pem")
            with open(private_key_path, 'wb') as f:
                f.write(self.private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            files['private_key'] = private_key_path

        if self.public_key:
            public_key_path = os.path.join(directory, f"{prefix}_public.pem")
            with open(public_key_path, 'wb') as f:
                f.write(self.public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ))
            files['public_key'] = public_key_path

        if self.certificate:
            cert_path = os.path.join(directory, f"{prefix}_certificate.pem")
            with open(cert_path, 'wb') as f:
                f.write(self.certificate.public_bytes(serialization.Encoding.PEM))
            files['certificate'] = cert_path

        return files

    def _calculate_hash(self, data: str) -> str:
        """Calculate SHA-256 hash of data."""
        import hashlib
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

    def get_certificate_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the loaded certificate.

        Returns:
            Dictionary with certificate information or None
        """
        if not self.certificate:
            return None

        return {
            'subject': str(self.certificate.subject),
            'issuer': str(self.certificate.issuer),
            'serial_number': str(self.certificate.serial_number),
            'not_valid_before': self.certificate.not_valid_before.isoformat(),
            'not_valid_after': self.certificate.not_valid_after.isoformat(),
            'signature_algorithm': self.certificate.signature_algorithm_oid._name,
            'version': self.certificate.version.name,
            'fingerprint_sha256': self.certificate.fingerprint(hashes.SHA256()).hex()
        }


class CertificateStore:
    """Manages certificate storage and retrieval."""

    def __init__(self, store_path: str = None):
        """
        Initialize certificate store.

        Args:
            store_path: Path to certificate store directory
        """
        if store_path is None:
            # Default to user config directory
            store_path = os.path.expanduser("~/.breaknwipe/certificates")

        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)

    def store_certificate(self, cert_id: str, certificate_data: Dict[str, Any]) -> str:
        """
        Store certificate data.

        Args:
            cert_id: Unique certificate identifier
            certificate_data: Certificate data to store

        Returns:
            Path to stored certificate file
        """
        cert_file = self.store_path / f"{cert_id}.json"

        with open(cert_file, 'w') as f:
            json.dump(certificate_data, f, indent=2)

        logger.info(f"Certificate stored: {cert_file}")
        return str(cert_file)

    def retrieve_certificate(self, cert_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve certificate data.

        Args:
            cert_id: Certificate identifier

        Returns:
            Certificate data or None if not found
        """
        cert_file = self.store_path / f"{cert_id}.json"

        if not cert_file.exists():
            return None

        try:
            with open(cert_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load certificate {cert_id}: {e}")
            return None

    def list_certificates(self) -> List[str]:
        """List all stored certificate IDs."""
        cert_files = list(self.store_path.glob("*.json"))
        return [f.stem for f in cert_files]

    def delete_certificate(self, cert_id: str) -> bool:
        """
        Delete certificate.

        Args:
            cert_id: Certificate identifier

        Returns:
            True if deleted successfully
        """
        cert_file = self.store_path / f"{cert_id}.json"

        try:
            cert_file.unlink()
            return True
        except Exception as e:
            logger.error(f"Failed to delete certificate {cert_id}: {e}")
            return False