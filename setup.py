import os
import random
import utils
from base import VoteLedger, VoterLedger
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa

# from consensus import Consensus
from base import Node, VotingComputer, BallotGenerator, VoterComputer, Block, VoterBlockchain, VoteBlockchain
from election import Voter, BallotItem, Choice


def set_up_nodes(NodeClass, num_nodes=50):
    """Generic function to create any type of Node specified, 
    set its network Nodes, and return a list of Nodes."""
    nodes = []
    node_mapping = dict()

    # create Nodes as well as public_key-node dictionary mapping
    for node in range(num_nodes):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=512,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        node = NodeClass(public_key, private_key)
        nodes.append(node)
        node_mapping[hash(public_key)] = node

    if num_nodes == 1:
        return nodes  # no need to set mapping for a single Node

    # pass key-node mapping of other Nodes in the network to each Node
    for node in nodes:
        node.set_node_mapping(dict(node_mapping))  # passes copy rather than reference
    return nodes


class VotingProgram:
    """Main voting program that sets up and runs election"""

    def set_up_election(self):
        # create (sample) election name & ballot content
        election = "2018 Election"
        candidates = [
            Choice("Hillary Clinton (D)"),
            Choice("Donald Trump (R)"),
            Choice("Gary Johnson (L)"),
            Choice("Jill Steel (G)")
        ]
        items = [
            BallotItem(
                title="President",
                max_choices=1,
                description="President of the United States",
                choices=candidates
            )
        ]

        candidates = [
            Choice("Joe Biden (D)"),
            Choice("Mike Pence (R)"),
        ]
        items.append(
            BallotItem (
                title="Vice President",
                max_choices=1,
                description="Vice President of the United States",
                choices=candidates
            )
        )

        # initialize blockchains for particular election

        # set up voting computers, voter computers, ballot generator w/ key pairs & blockchain instances
        num_nodes = 5
        print('Setting up voting computers, voter computers, and ballot generator')
        self.voting_computers = set_up_nodes(VotingComputer, num_nodes=num_nodes)
        self.voter_computers = set_up_nodes(VoterComputer, num_nodes=num_nodes)
        self.ballot_generator = set_up_nodes(BallotGenerator, num_nodes=1)[0]
        # give ballot generator mapping of voting computers
        self.ballot_generator.set_node_mapping(
            {hash(node.public_key): node for node in
             self.voting_computers}
        )  # give ballot generator mapping of voting computers

        # set ballot generator for each voting computer
        for voting_computer in self.voting_computers:
            voting_computer.set_ballot_generator(self.ballot_generator)

        # TODO: construct adversary nodes & add to network
        adversary_node = set_up_nodes(VotingComputer, num_nodes=2)

        # create finalized voter roll
        # The people who are actually allowed to vote / registered to vote
        print('Finalizing voter roll')
        self.voter_roll = [Voter('Mateusz Gembarzewski', '1'),
                           Voter('Jai Punjwani', '2')]

        # generate ballots using the election and ballot content. generate same number of ballots as registered voters
        # Each Voter who becomes validated to vote should receive 1 ballot.
        print('Voter registration closed. Generating {} ballots'.format(len(self.voter_roll)))
        ballots = self.ballot_generator.generate_ballots(election, items, num_ballots=len(self.voter_roll))

        # ensure that ballot IDs are unique by adding all IDs to a master set & checking that set length = ballot list length
        ballot_ids = set()
        for ballot in ballots:
            ballot_ids.add(ballot.id)

        if len(ballot_ids) != len(ballots):
            raise Exception("Generated non-unique ballot")

        # holds filled out ballots. TODO: use this
        self.paper_trail = []

        # initialize ledgers; CAVEAT: each node will need its own ledger
        voter_ledger = VoterLedger(self.voter_roll)
        vote_ledger = VoteLedger(ballots)

        # initialize blockchains for each node
        voter_blockchain = VoterBlockchain(voter_ledger)
        vote_blockchain = VoteBlockchain(vote_ledger)

    def begin_election(self):
        """Main entry point to begin the election program"""
        exit = False
        print('Start of election!')
        ballots_available = True
        while not exit and ballots_available:
            self.clear_screen()
            self.print_menu()
            menu_choice = utils.get_input_of_type("Please enter choice:", int)
            exit = self.handle_input(menu_choice)
            ballots_available = False if not self.ballot_generator.are_ballots_available() else True
        print('Election Over!')

        # TODO: at end of election call consensus protocol to send transactions & tally

        # annouce results?

    def print_menu(self):
        print("(1) Vote")
        print("(2) View Current Results")
        print("(3) View Logs")
        print("(4) Inspect Ledger")
        print("(5) exit")
        print()

    def clear_screen(self):
        os.system('cls||clear')

    def handle_input(self, menu_number):
        """Redirects user to appropriate method and returns whether or not program should exit"""
        if menu_number == 5:
            return True
        elif menu_number == 4:
            pass
        elif menu_number == 3:
            pass
        elif menu_number == 2:
            pass
        elif menu_number == 1:
            self.begin_voting_process()
        return False  # meaning that program will not exit

    def begin_voting_process(self):
        for voter in self.voter_roll:
            print(voter.id, voter.name)

        # Allow user to self-authenticate
        voter_id = utils.get_input_of_type("Please enter your voter ID: ", str)
        voter = self.get_voter_by_id(voter_id)
        if not voter:
            print("Incorrect ID entered.")
            return

        # check that voter has not voted before
        voter_computer = random.choice(self.voter_computers)
        voted = voter_computer.has_voter_voted(voter)
        if voted:
            print('You have already voted!')
            return

        # voter has not voted; retrieve a ballot from the ballot generator
        ballot = self.ballot_generator.retrieve_ballot()  # this will create a transaction for the ballot as well
        print('your ballot id: ' + str(ballot.id))

        # create transaction on voter computer indicating that voter has retrieved ballot (we say that they voted)
        print('Creating transaction on voter blockchain')
        voter_computer.create_transaction(voter)

        # voter visits random voting computer
        voting_computer = random.choice(self.voting_computers)
        print('Now at voting booth')
        
        # voter fills out ballot and confirms choice
        self.process_ballot(ballot)
        ballot_filled = ballot.is_filled()

        # ensures that ballot is filled
        while not ballot_filled:
            self.process_ballot(ballot)
            ballot_filled = ballot.is_filled()
        input("Press enter to submit your ballot")

        # submit ballot to paper trail
        self.paper_trail.append(ballot)

        # simulation does not offer the chance for voter to omit ballot not change it; maybe request a new one?

        # TODO: handle state of select/chosen for multi-choice options

        # self.paper_trail.append(ballot)

        # create a transaction with the ballot
        voting_computer.create_transaction(ballot)
        print("Created a transaction with the ballot and the ballot state.")

    def get_voter_by_id(self, id):
        """Getting voter name via provided ID"""
        for voter in self.voter_roll:
            if voter.id == id:
                return voter
        return None

    def print_ballot(self, ballot):
        """Prints out ballot"""
        for item in ballot.items:
            choice_num = 1
            for choice in item.choices:
                print(choice_num, ":", choice.description)
                choice_num = choice_num + 1

    def process_ballot(self, ballot):
        """Prints out each ballot item and allows user to select and verify a choice for each"""
        for item in ballot.items:
            # skip BallotItems that cannot be filled out any more
            if item.max_choices_selected():
                continue

            choice_num = 1
            print(item.description)
            for choice in item.choices:
                choice_str_list = [str(choice_num), ':', choice.description]
                if choice.chosen:
                    choice_str_list.append('SELECTED')
                print(" ".join(choice_str_list))
                choice_num = choice_num + 1

            candidate_selection = utils.get_input_of_type("Please enter the number of the candidate to bubble in your optical scan ballot: ", 
                                                          int, 
                                                          list(range(1, len(item.choices)+1))
            )
            candidate_index = candidate_selection - 1
            confirmed = utils.get_input_of_type("Enter 'y' to confirm selection or 'n' to reject. " + item.choices[candidate_index].description + ": ",
                                                str,
                                                ['y','n']
            )
            if confirmed == 'y':
                item.choices[candidate_index].select()
            else:
                # prompt user to re-select
                # item.clear()  # clear the BallotItem so it can be filled all at once (for simplicity)
                pass

    def show_consensus(self):
        """Demonstrates consensus for both VoterBlockchain and VoteBlockchain"""
        # all voting computers broadcast transactions (includes timestamping & signing)
        for voting_computer in self.voting_computers:
            voting_computers.broadcast_transactions()

        # now all nodes have a list of their approved transactions
        # each node gets copy of last ledger from last block
        # & applies approved transactions to the copy of that ledger

        # now node obtains a hash of the new ledger, and sends it to all nodes and counts approvals
        # if enough approvals, node creates block w/ txs, updated ledger. Block is added to blockchain
        # if not [out of scope, this won't happen unless we simulate MANY adversaries or network delays]
        

    # show that voting process works; print out consensus process

    # show voter statistical delay process: [out of scope? since we won't really have enough votes]

    # show that if node tries to change history, then the others reject it

    # simulate lost transactions to some nodes (add receive tx method to node; and randomly decide if it

    # will lose the transaction or not. Then demonstrate that this doesn't matter since nodes will have an amalgamated

    # list of transactions during the consensus round

    # show that if some ballots are corrupted or withheld electronically, then the paper ballot serves as a good backup

    # IDEA: run a normal election; then simulate the election with adversary nodes and show how it would still succeed
