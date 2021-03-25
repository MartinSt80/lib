
import string, random

chars = string.ascii_letters + string.digits + string.punctuation.replace("=", "")

print(''.join(random.choice(chars) for _ in range(16)))