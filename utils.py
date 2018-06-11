import base
import election
import hashlib
from copy import deepcopy
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa



# TODO: explore alternate options for rsa. Currently, private key is required
# for decryption. Or, try using rsa.sign/rsa.verify (which hashes first, then signs).
# only issue there is we need to figure out how to verify the contents of something that was signed
# easy.. we generate the contents for each entity that we sign, then later generate the same expected content, 
# pass that into verify and we have checked 2 things (1): source authenticity and (2) non-tampered data
# for the voteTransaction, which has to be signed with non timestamped content, then resigned with timestamped content,
# can be done easily as well. timestamped = True; this changes the message content to sign (and thus for verifying)
# additionally: to get the content of an object, just override __str__

def sign(message, private_key):
    if type(message) == str:
        message = message.encode()

    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    return signature


def verify_signature(message, signature, public_key):
    """Returns whether or not signature/public key matches expected message hash"""
    if type(message) == str:
        message = message.encode()
    try:
        public_key.verify(
            signature,
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except InvalidSignature:
        print('signature failed validation!')
    except Exception:
        pass
    return False


def get_hash(obj):
    """Returns the hash (string, as hexadecimal digest) of the object based on its type."""
    hash_func = hashlib.sha1  # not secure hash function, but used here for memory purposes
    hash_message = str(obj).encode()
    return hash_func(hash_message).hexdigest()


def get_formatted_time_str(date_obj):
    """Returns a string representation of a date object as Y-M-D H:M"""
    return date_obj.strftime("%Y-%m-%d %H:%M")


def get_input_of_type(message, expected_type, allowed_inputs=None):
    """Generic function to receive user input of an expected type and restrict to a subset of inputs"""
    while True:
        try:
            user_input = expected_type(input(message))
            if allowed_inputs:
                if user_input in allowed_inputs:
                    break   # correct input type and part of allowed inputs
                print('Unexpected input')
                continue
            break
        except:
            print("Wrong type of input")
    return user_input


def get_deep_copy_of_list(objects):
    """Takes in a list of objects and returns a newly constructed list of (deep) copied objects."""
    new_list = []
    for obj in objects:
        new_list.append(deepcopy(obj))
    return new_list