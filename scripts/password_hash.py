"""Original BCrypt-compatible utility; does not modify users or print plaintext."""
from getpass import getpass
import bcrypt

if __name__ == "__main__":
    password = getpass("Password: ")
    if password != getpass("Confirm password: "):
        raise SystemExit("Passwords differ")
    print(bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(10, prefix=b"2a")).decode())
