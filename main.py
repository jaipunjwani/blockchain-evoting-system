from setup import VotingProgram


def main():
    program = VotingProgram()
    program.set_up_election()
    program.begin_election()


if __name__ == '__main__':
    main()
