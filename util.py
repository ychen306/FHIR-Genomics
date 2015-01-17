import uuid
import hashlib

def hash_password(password, salt=None):
    if salt is None:
        salt = uuid.uuid4().hex
    hashed = hashlib.sha512(password + salt).hexdigest()
    return hashed, salt
