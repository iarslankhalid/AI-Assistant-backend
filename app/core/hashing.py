from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class Hasher:
    @staticmethod
    def _truncate_password(password: str) -> str:
        """
        Truncate password to 72 bytes for bcrypt compatibility.
        Ensures we don't break multi-byte UTF-8 characters.
        """
        encoded = password.encode('utf-8')
        if len(encoded) <= 72:
            return password
        
        # Truncate and ensure valid UTF-8
        truncated = encoded[:72]
        # Remove any incomplete multi-byte character at the end
        while truncated:
            try:
                return truncated.decode('utf-8')
            except UnicodeDecodeError:
                truncated = truncated[:-1]
        return ""
    
    @staticmethod
    def hash_password(password: str):
        password = Hasher._truncate_password(password)
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password, hashed_password):
        plain_password = Hasher._truncate_password(plain_password)
        return pwd_context.verify(plain_password, hashed_password)
