"""Minimal software authenticator for exercising passkey flows in tests.

It produces real WebAuthn responses (attestation "none", ES256), so the backend
verifies them exactly like responses from a real device.
"""

import hashlib
import json
import os
import struct
from dataclasses import dataclass, field

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, encode_cbor

FLAG_UP = 0x01  # user present
FLAG_UV = 0x04  # user verified
FLAG_AT = 0x40  # attested credential data included


@dataclass
class SoftAuthenticator:
    origin: str = "http://localhost:5173"
    credential_id: bytes = field(default_factory=lambda: os.urandom(32))
    private_key: ec.EllipticCurvePrivateKey = field(
        default_factory=lambda: ec.generate_private_key(ec.SECP256R1())
    )
    sign_count: int = 0
    user_handle: bytes | None = None

    def create(self, options: dict) -> dict:
        """Equivalent of `navigator.credentials.create()`."""
        self.user_handle = base64url_to_bytes(options["user"]["id"])
        client_data = self._client_data("webauthn.create", options["challenge"])
        numbers = self.private_key.public_key().public_numbers()
        cose_key = {
            1: 2,  # kty: EC2
            3: -7,  # alg: ES256
            -1: 1,  # crv: P-256
            -2: numbers.x.to_bytes(32, "big"),
            -3: numbers.y.to_bytes(32, "big"),
        }
        attested = (
            bytes(16)  # AAGUID
            + struct.pack(">H", len(self.credential_id))
            + self.credential_id
            + encode_cbor(cose_key)
        )
        auth_data = self._auth_data(options["rp"]["id"], FLAG_UP | FLAG_UV | FLAG_AT) + attested
        attestation = encode_cbor({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": bytes_to_base64url(self.credential_id),
            "rawId": bytes_to_base64url(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "attestationObject": bytes_to_base64url(attestation),
                "transports": ["internal"],
            },
            "clientExtensionResults": {},
            "authenticatorAttachment": "platform",
        }

    def get(self, options: dict) -> dict:
        """Equivalent of `navigator.credentials.get()` (discoverable credential)."""
        client_data = self._client_data("webauthn.get", options["challenge"])
        self.sign_count += 1
        auth_data = self._auth_data(options["rpId"], FLAG_UP | FLAG_UV)
        signature = self.private_key.sign(
            auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256())
        )
        assert self.user_handle is not None
        return {
            "id": bytes_to_base64url(self.credential_id),
            "rawId": bytes_to_base64url(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "authenticatorData": bytes_to_base64url(auth_data),
                "signature": bytes_to_base64url(signature),
                "userHandle": bytes_to_base64url(self.user_handle),
            },
            "clientExtensionResults": {},
        }

    def _client_data(self, type_: str, challenge: str) -> bytes:
        return json.dumps(
            {"type": type_, "challenge": challenge, "origin": self.origin, "crossOrigin": False}
        ).encode()

    def _auth_data(self, rp_id: str, flags: int) -> bytes:
        rp_id_hash = hashlib.sha256(rp_id.encode()).digest()
        return rp_id_hash + bytes([flags]) + struct.pack(">I", self.sign_count)
