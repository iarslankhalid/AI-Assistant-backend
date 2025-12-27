from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class Hasher:
    @staticmethod
    def hash_password(password: str):
        # Truncate to 72 bytes to comply with bcrypt's limitation
        password_bytes = password.encode('utf-8')[:72]
        return pwd_context.hash(password_bytes.decode('utf-8', errors='ignore'))

    @staticmethod
    def verify_password(plain_password, hashed_password):
        # Truncate to 72 bytes to comply with bcrypt's limitation
        password_bytes = plain_password.encode('utf-8')[:72]
        return pwd_context.verify(password_bytes.decode('utf-8', errors='ignore'), hashed_password)
