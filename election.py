# TODO: design configuration for secret/non-secret vote
import random
from constants import STATE
from copy import deepcopy


class Voter:
    """Simple voter class with a name and unique ID"""

    def __init__(self, name, voter_id):
        self.name = name
        self.id = voter_id  # must be unique
        self.state = STATE.NOT_VOTED

    def __str__(self):
        return self.id

    def get_signature_contents(self, **kwargs):
        return self.id

    # TODO: remove state from voter & ballot ledger holds the current state or truth
    # however, ballot: created->issued & issued-> used are submitted together, but the
    # truth on the ledger at both times are 'created'
    def vote(self):
        self.state = STATE.VOTED


class Choice:
    """Represents a ballot choice. For example, `Barack Obama (D)` would be a choice
    for the 2012 Presidential Election ballot."""

    def __init__(self, description):
        self.description = description
        self.chosen = False

    def __str__(self):
        return ":".join([self.description, str(self.chosen)])

    def get_signature_contents(self, include_chosen=True):
        """Gets the description of a choice and (by default) whether it was chosen. The latter can be 
        overridden (useful for transaction signature of a ballot that was newly created and later filled)."""
        content_list = [self.description]
        if include_chosen:
            content_list.append(str(self.chosen))
        return ":".join(content_list)

    def select(self):
        self.chosen = True

    def unselect(self):
        self.chosen = False


class BallotItem:
    """Represents an item or a POSITION in an election that is represented on a ballot. Ballots can have multiple
    BallotItems that voters can vote on. Moreover, a ballot item can allow one or more selections."""

    def __init__(self, title, description, max_choices, choices):
        self.title = title
        self.description = description
        self.max_choices = max_choices
        self.choices = choices

    def __deepcopy__(self, memo):
        """Creates deep copy of Ballot Item. 
        Code from: https://stackoverflow.com/questions/1500718/what-is-the-right-way-to-override-the-copy-deepcopy-operations-on-an-object-in-p"""
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            setattr(result, k, deepcopy(v, memo))
        return result

    def __str__(self):
        str_list = [self.title, self.description, str(self.max_choices)]
        for choice in self.choices:
            str_list.append(str(choice))
        return ":".join(str_list)

    def get_signature_contents(self, **signature_kwargs):
        str_list = [self.title, self.description, str(self.max_choices)]
        for choice in self.choices:
            str_list.append(choice.get_signature_contents(**signature_kwargs))
        return ":".join(str_list)

    def clear(self):
        """Unselects all choices"""
        for choice in self.choices:
            choice.unselect()

    def max_choices_selected(self):
        """Returns whether or not the maximum number of choices is selected."""
        selected = 0
        for choice in self.choices:
            if choice.chosen:
                selected = selected + 1
            if selected == self.max_choices:
                return True
        return False

    def vote(self, choice_description):
        # find appropriate item
        for i in self.choices:
            # once it matches then that is who the voter voted for
            if choice_description == i.description:
                i.select()


class Ballot:
    """Ballot used to indicate votes for election
    TODO: reassess design"""

    def __init__(self, election, items):
        self.id = str(random.getrandbits(128))  # assign a random ID to the ballot
        self.election = election
        self.items = items

    def __str__(self):
        str_list = [self.id, self.election]
        for item in self.items:
            str_list.append(str(item))
        return ":".join(str_list)

    def get_signature_contents(self, **signature_kwargs):
        str_list = [self.id, self.election]
        for item in self.items:
            str_list.append(item.get_signature_contents(**signature_kwargs))
        return ":".join(str_list)        

    def is_filled(self):
        """Returns whether or not each BallotItem has at least one selected choice"""
        for item in self.items:
            item_filled = False
            for choice in item.choices:
                if choice.chosen:
                    item_filled = True
                    break
            if not item_filled:
                return False
        return True  # all BallotItems have been checked   

    def get_selected_choices(self):
        selected_choices = []
        for item in self.items:
            for choice in item.choices:
                if choice.chosen:
                    selected_choices.append(choice)
        return selected_choices
                    

    # possibly rename to fill() - since blockchain will be officially recording that ballot was used
    def vote(self, title, option):
        for item in Ballot.items:  # for each item in ballot.items
            if title == item.title:  # if the titles ever match in the iteration
                for choice in item.choices:  # then for every X in option
                    if choice == option:
                        item.vote(option)  # vote for candidate X
