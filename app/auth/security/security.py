import bcrypt 

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    encoded_password = password.encode('utf-8')
    hashed_password = bcrypt.hashpw(encoded_password, salt)
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    encoded_hashed_password = hashed_password.encode('utf-8')       
    encoded_plain_password = plain_password.encode('utf-8')

    return bcrypt.checkpw(encoded_hashed_password, encoded_plain_password)

