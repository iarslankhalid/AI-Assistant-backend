import bcrypt

class Hasher:
    @staticmethod
    def _truncate_password(password: str) -> bytes:
        """
        Truncate password to 72 bytes for bcrypt compatibility.
        Returns bytes.
        """
        encoded = password.encode('utf-8')
        if len(encoded) <= 72:
            return encoded
        
        # Truncate and ensure valid UTF-8
        truncated = encoded[:72]
        # Remove any incomplete multi-byte character at the end
        while truncated:
            try:
                truncated.decode('utf-8')
                return truncated
            except UnicodeDecodeError:
                truncated = truncated[:-1]
        return b""
    
    @staticmethod
    def hash_password(password: str) -> str:
        password_bytes = Hasher._truncate_password(password)
        # bcrypt.hashpw returns bytes, we need str for storage
        hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
        return hashed.decode('utf-8')

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        password_bytes = Hasher._truncate_password(plain_password)
        if isinstance(hashed_password, str):
            hashed_password = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_password)
