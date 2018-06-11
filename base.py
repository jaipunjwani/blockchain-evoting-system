import datetime
import random
import utils
from constants import STATE
from copy import deepcopy
from election import Ballot, Voter


class Node:
    """Abstract class for node that participates in a blockchain"""

    def __init__(self, public_key, private_key):
        self.public_key = public_key
        self._private_key = private_key
        self.verified_transactions = set()  # transactions that were verified. includes created transactions
        self.rejected_transactions = set()  # transactions that were rejected. may be marked for not counting

    def set_node_mapping(self, node_dict):
        """Sets mapping for public key addresses to each node in the network"""
        node_dict.pop(hash(self.public_key), None)  # remove current node's own mapping
        self.node_mapping = node_dict

    def create_transaction(self):
        """Abstract method that to allow node to create transaction specific to blockchain. Should return boolean indicating success"""
        pass

    def broadcast_transactions(self, transactions):
        """Abstract method to allow node to broadcast transactions to other nodes"""
        pass

    def add_transaction(self, transaction):
        """Verifies an incoming transaction and adds it to the local computer"""
        # check that source is trusted and validate transaction
        valid = self.is_node_in_network(transaction.node.public_key) and Transaction.verify_transaction(transaction)
        if valid:
            if not transaction.timestamped:
                # only for untimestamped vote transactions
                self.pending_transactions.add(transaction)
            else:
                self.verified_transactions.add(transaction)
        else:
            print('transaction was rejected!')
            self.rejected_transactions.add(transaction)

    def create_block(self):
        """"""
        pass

    def is_node_in_network(self, public_key):
        """Returns whether or not public key is one of the recognized nodes"""
        return hash(public_key) in self.node_mapping

    def sign_message(self, message):
        """Signs a string or bytes message using the RSA algorithm"""
        return utils.sign(message, self._private_key)


class VotingComputer(Node):
    """Node that handles the casting of votes. The VotingComputer verifies ballots,
    signs them, and participates in the VoteBlockchain"""

    def __init__(self, *args):
        super(VotingComputer, self).__init__(*args)
        self.pending_transactions = set()  # transactions waiting to be timestamped and broadcasted
    
    def set_ballot_generator(self, ballot_generator):
        """Stores reference to ballot generator so that VotingComputer accepts its transactions"""
        self.ballot_generator = ballot_generator

    def is_node_in_network(self, public_key):
        """Returns whether or not public key belongs to one of the recognized nodes OR the ballot generator."""
        return hash(public_key) in self.node_mapping or public_key == self.ballot_generator.public_key

    def validate_ballot(self, ballot):
        """Ensures that ballot is legitimate and filled out properly and returns boolean for validity"""
        # TODO: use blockchain/ latest ledger to check whether ballot ID is present
        # check that ballot ID is legit and that it has not been used
        # check that the ballot contents are valid - meaning that the voter selected
        # the required number of choice(s)
        pass

    def create_transaction(self, ballot):
        """Creates an untimestamped transaction and adds to pending list of transactions"""
        # checks whether or not ballot was issued. Note: ballot issuance transactions are only broadcasted with
        # the corresponding ballot_used transaction
        ballot_issued = False
        for transaction in self.pending_transactions:
            if transaction.content.id == ballot.id and transaction.new_state == STATE.ISSUED:
                ballot_issued = True

        if ballot_issued:
            tx = VoteTransaction(ballot, self, STATE.ISSUED, STATE.USED, timestamped=False)
            self.pending_transactions.add(tx)
            return True
        else:
            print('ballot was never issued!')
            return False

    def broadcast_transactions(self):
        """Timestamps, signs and sends pending transactions to all nodes (once there is enough statistical variation)"""
        VoteTransaction.timestamp_and_sign_transactions(self.pending_transactions)
        for tx in self.pending_transactions:
            self.add_transaction(tx)  # treats pending transaction as an incoming transaction
            for node in self.node_mapping.values():
                node.add_transaction(tx)
        self.pending_transactions = set()  # reset


class VoterComputer(Node):
    """Node that handles the authentication of voters and ensure that they only vote once. 
    The VoterComputer participates in the VoterBlockchain and is responsible for """

    def authenticate_voter(self, voter, voter_roll):
        """Returns whether or not voter is registered in voter roll"""
        if voter in voter_roll:
            print(voter.name + ' authenticated')
            return True
        else:
            print(voter.name + ' not on voter roll')
            return False

    def has_voter_voted(self, voter):
        """Returns whether (authenticated) voter has voted"""
        # check whether or not voter is on local transactions or voter blockchain
        pass

    def create_transaction(self, voter):
        tx = VoterTransaction(voter, self, STATE.NOT_VOTED, STATE.VOTED, timestamped=True)
        # computer automatically verifies self-created transactions
        self.verified_transactions.add(tx)
        # broadcast to nodes right away
        self.broadcast_transactions([tx])
        return True

    def broadcast_transactions(self, transactions):
        for transaction in transactions:
            for node in self.node_mapping.values():
                node.add_transaction(transaction)


class AdversaryVotingComputer(VotingComputer):
    """VotingComputer that has malicious behavior. TODO: add behavior change"""


class AdversaryVoterComputer(VoterComputer):
    """VoterComputer that has malicious behavior"""

    def has_voter_voted(self, voter):
        """Always returns False to allow voters to vote multiple times"""
        return False


class BallotGenerator(Node):
    """Computer that generates ballots and notifies voting computers for each ballot's creation."""

    def generate_ballots(self, election, items, num_ballots=None):
        """Generates & returns list of ballots. This takes place before election day."""
        ballots = []
        if num_ballots:
            for i in range(num_ballots):
                ballots.append(Ballot(election, utils.get_deep_copy_of_list(items)))
        self.ballots = tuple(ballots)  # master list
        self.available_ballots = list(ballots)
        return ballots

    def are_ballots_available(self):
        return len(self.available_ballots) > 0

    def retrieve_ballot(self):
        """Returns a random ballot and creates transaction for change in ballot state"""
        if self.are_ballots_available():
            ballot = random.choice(self.available_ballots)      
            self.available_ballots.remove(ballot)
            # create transaction and notify all voting computers
            self.create_transaction(ballot)
            return ballot
        return None

    def is_legitimate_ballot(self, ballot):
        """Returns whether ballot was generated by BallotGenerator"""
        return ballot in self.ballots

    def create_transaction(self, ballot):
        """Creates (untimestamped) transaction indicating that ballot was issued and sends this to all voting computers."""
        tx = VoteTransaction(ballot, self, STATE.CREATED, STATE.ISSUED, timestamped=False, include_chosen=False)
        # add transaction to all voting machines
        for voting_machine in self.node_mapping.values():
            voting_machine.add_transaction(tx)
        return True


class Transaction:
    """A change of state for an entity or object. Transactions are signed, and may
    or may not be timestamped. Here state loosely correlates to address or owner. For example, 
    I can cast a ballot to "Barack Obama" - which would be the new state of my ballot"""

    allowed_states = None  # will define valid states for the transaction
    timestamped = True  # by default, all Transactions are timestamped
    content_class = None  # defines the expected class of the content

    def __init__(self, content, node, previous_state, new_state, timestamped=timestamped, **signature_kwargs):
        """Transaction consists of some content, an issuing node (public key), the signed
        content(including timestamp), and depending on the use case, a timestamp, which is 
        enabled by default

        Args:
            content             the object whose state is being tracked in the transaction
            node                the Node that creates the transaction
            previous_state      the previous state of the content
            new_state           the new state of the content
            timestamped         whether or not this transaction should be timestamped
            signature_kwargs    key word arguments to control signature
        """
        if type(content) is not self.content_class:
            raise Exception('Unexpected transaction content!')
        if getattr(content, 'get_signature_contents') is None:
            raise Exception(str(content_class) + ' needs to implement method get_signature_contents')
        self.content = content
        self.signature_kwargs = signature_kwargs
        if previous_state in self.allowed_states and new_state in self.allowed_states:
            self.previous_state = previous_state
            self.new_state = new_state
        else:
            raise Exception("Invalid state for transaction..add to tamper log?")
        self.node = node
        self.timestamped = timestamped
        if timestamped:
            self.time = datetime.datetime.now()
        self.signature = node.sign_message(self.get_signature_contents(**self.signature_kwargs))

    def get_signature_contents(self, **signature_kwargs):
        """Produces unique string representation of a transaction which is then signed. 
        Adds timestamp if present."""
        str_list = [self.content.get_signature_contents(**signature_kwargs),
                    self.previous_state,
                    self.new_state]
        if self.timestamped:
            str_list.append(self.get_time_str())
        return ":".join(str_list)

    def __str__(self):
        return str(self.signature)

    def get_time_str(self):
        if self.timestamped:
            return utils.get_formatted_time_str(self.time)
        return None

    @staticmethod
    def verify_transaction(transaction):
        """Validates a transaction's signature and returns whether its content matches its hash"""
        return utils.verify_signature(transaction.get_signature_contents(**transaction.signature_kwargs), transaction.signature, transaction.node.public_key)


class VoteTransaction(Transaction):
    """Class for transactions related to the state of ballots"""
    allowed_states = [STATE.CREATED, STATE.ISSUED, STATE.USED]
    timestamped = False  # we do not timestamp vote transactions when they are created
    content_class = Ballot

    def add_timestamp(self, time=None):
        """Adds a timestamp to a transaction when it is ready to be signed again"""
        self.time = time or datetime.datetime.now()
        self.timestamped = True

    @staticmethod
    def timestamp_and_sign_transactions(transactions):
        """Adds a timestamp to each transaction and signs it for the second time. This is used for vote
        transactions that are ready to be timestamped and broadcasted (i.e., there is enough statistical 
        disparity in the voter-vote links). Note that the timestamp is included in the signature."""
        now = datetime.datetime.now()
        for tx in transactions:
            tx.add_timestamp(time=now)
            # overwrite old signature
            tx.signature = tx.node.sign_message(tx.get_signature_contents()) 


class VoterTransaction(Transaction):
    """Class for transactions related to the state of voters"""
    allowed_states = [STATE.NOT_VOTED, STATE.VOTED]
    content_class = Voter


class Ledger:
    """Abstract ledger class that stores the current overall result of transactions
    Note that the ledger is only updated by the blockchain when consensus has been achieved."""

    def __init__(self):
        self.ledger = dict()

    def get_copy(self):
        """Returns copy of ledger object. This is useful in blocks, which contains its own ledger."""
        return deepcopy(self)

    def get_hash(self):
        """Returns unique hash of Ledger"""
        return hash(str(self.ledger))


class VoteLedger(Ledger):
    """Ledger that stores state of ballots, total votes for candidates as well as collective 
    totals of created, issued, and used ballots."""

    def __init__(self, ballots):
        """
        Args:
            ballots         list of Ballot objects. Assumes each ballot has the same content.
        """
        super(VoteLedger, self).__init__()
        self.total_ballots = len(ballots)
        
        # add state of individual ballots
        for ballot in ballots:
            self.ledger[ballot] = STATE.CREATED    

        # add collective ballot totals
        self.ledger[STATE.CREATED] = self.total_ballots
        self.ledger[STATE.ISSUED] = 0
        self.ledger[STATE.USED] = 0

        # extract candidates from ballots and initialize their vote count to 0
        candidades = []
        for item in ballots[0].items:
            for candidate in item.choices:
                self.ledger[candidate] = 0

    def apply_transactions(self, transactions):
        """Updates the ledger based on the provided transactions. Note: Two logical types of transactions can
        be applied to ballots: tx: ballot.created -> ballot.issued and tx: ballot.issued -> ballot.used. They 
        must be applied in the specified order; transactions passed here are not guaranteed to be in the right
        order. That is why we loop over the transactions twice.
        
        Args:
            transactions        list of VoteTransaction objects
        """
        for iteration in range(2):    
            for transaction in transactions:
                if iteration == 1 and transaction._reiterate is False:
                    continue

                ballot = transaction.content
                old_state = self.ledger[ballot]
                tx_previous_state = transaction.previous_state
                tx_new_state = transaction.new_state

                if tx_previous_state != old_state:
                    # if transaction does not line up with ledger state, mark so that we come back to it
                    transaction._reiterate = True
                    continue
                
                # update individual ballot state
                self.ledger[ballot] = tx_new_state

                # update collective ballots
                self.ledger[old_state] = self.ledger[old_state] - 1
                self.ledger[tx_new_state] = self.ledger[tx_new_state] + 1

                # update candidate votes
                candidates = ballot.get_selected_choices()
                for candidate in candidates:
                    self.ledger[candidate] = self.ledger[candidate] + 1
                
                transaction._reiterate = False


class VoterLedger(Ledger):
    """Ledger that stores individual voters and whether or not they voted as well as 
    the collective totals for voters that have voted/not voted."""

    def __init__(self, voters):
        """
        Args:
            voters          list of Voter objects
        """
        super(VoterLedger, self).__init__()
        num_voters = len(voters)
        
        # add collective totals to ledger
        self.registered_voters = num_voters
        self.ledger[STATE.NOT_VOTED] = num_voters
        self.ledger[STATE.VOTED] = 0

        # add state of individual voters to ledger
        for voter in voters:
            self.ledger[voter] = STATE.NOT_VOTED


    def apply_transactions(self, transactions):
        """Updates the ledger based on the provided transactions.
        Args:
            transactions    list of VoterTransaction objects
        """
        for transaction in transactions:
            voter = transaction.content
            current_state = self.ledger[voter]
            tx_previous_state = transaction.previous_state
            tx_new_state = transaction.new_state

            if current_state != tx_previous_state:
                continue

            # update voter state
            self.ledger[voter] = tx_new_state

            # update collective totals
            self.ledger[tx_previous_state] = self.ledger[tx_previous_state] - 1
            self.ledger[tx_new_state] = self.ledger[tx_new_state] + 1


class Block:
    """Block in a blockchain that contains transactions and references the previous block, if any."""
    ledger_class = None

    def __init__(self, transactions, ledger, node, prev_block=None):
        self.transactions = transactions
        self.previous_block = prev_block

        if type(ledger) is not self.ledger_class:
            raise('Wrong type of ledger')

        self.ledger = ledger  # current ledger at time of creation of block
        self.time = datetime.datetime.now()
        self.header = node.sign_message(Block.get_hash(self))
        self.node = node

    def __eq__(self, other):
        return self.header == other.header

    def get_signature_contents(self, **signature_kwargs):
        """"""
        str_list = []
        if self.previous_block:
            str_list.append(self.previous_block.header)
        else:
            str_list.append('')  # no previous block
        
        for tx in block.transactions:
            # get the hash of each transaction, append to digest
            str_list.append(tx.signature.decode())
        str_list.append(self.ledger.get_hash())
        str_list.append(utils.get_formatted_time_str(self.time))  # add time
        hash_content = ":".join(str_list)
        return hash_content

    def is_genesis_block(self):
        """Returns whether block is the first (genesis) block in the blockchain"""
        if self.previous_block:
            return True
        return False

    # TODO: genesis block should be the block that you start off with (the initial state of everything)


class VoteBlock(Block):
    """Block that is stored in VoteBlockchain."""
    ledger_class = VoteLedger


class VoterBlock(Block):
    """Block that is stored in VoterBlockchain."""
    ledger_class = VoterLedger


class Blockchain:
    """Abstract Blockchain class. Note: Blockchain will run protocol that manages
    network consensus as well as updating the ledger"""

    def __init__(self, initial_ledger):
        self.current_ledger = initial_ledger
        self.current_block = None

    def add_block(self, block):
        """Checks that block builds off current root block and adds it to blockchain"""
        # check that block's previous
        if block.previous_block is self.current_block:
            self.current_block = block
        else:
            print('block rejected. must build off current block')
    
    def add_block_2(self, block):
        """Checks that block builds off current root block and adds it to blockchain"""
        # check that block's previous
        block.previous_block = self.current_block
        self.current_block = block

    def remove_block(self, block):
        """Should never be called."""
        raise Exception('The blockchain does not allow removing blocks as it serves as an audit trail. Append blocks correcting any mistakes, if any.')


class VoteBlockchain(Blockchain):
    """Blockchain that tracks ballots/votes.."""


class VoterBlockchain(Blockchain):
    """Blockchain that tracks voters."""
