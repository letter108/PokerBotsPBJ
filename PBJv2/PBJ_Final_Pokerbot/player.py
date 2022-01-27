'''
Simple example pokerbot, written in Python.
'''
from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction
from skeleton.states import GameState, TerminalState, RoundState
from skeleton.states import NUM_ROUNDS, STARTING_STACK, BIG_BLIND, SMALL_BLIND
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot

import random 
import eval7
import pandas as pd


class Player(Bot):
    '''
    A pokerbot.
    '''

    def __init__(self):
        '''
        Called when a new game starts. Called exactly once.

        Arguments:
        Nothing.

        Returns:
        Nothing.
        '''

        self.myDelta = 0
        self.prevStrength = 0.5
        self.raisePreFlopVar = 0.4
        self.raisePostFlopVar = 0.7
        self.opp_prev_cards = []
        self.prev_end_round = 5
        self.scaryOffset = 0

        #make sure this df isn't too big!! Loading data all at once might be slow if you did more computations!
        calculated_df = pd.read_csv('hole_strengths.csv') #the values we computed offline, this df is slow to search through though
        holes = calculated_df.Holes #the columns of our spreadsheet
        strengths = calculated_df.Strengths
        self.starting_strengths = dict(zip(holes, strengths)) #convert to a dictionary, O(1) lookup time!
        
    def calc_strength(self, hole, iters, community = []):
        ''' 
        Using MC with iterations to evalute hand strength 

        Args: 
        hole - our hole carsd 
        iters - number of times we run MC 
        community - community cards
        '''

        deck = eval7.Deck() # deck of cards
        hole_cards = [eval7.Card(card) for card in hole] # our hole cards in eval7 friendly format

        if community != []:
            community_cards = [eval7.Card(card) for card in community]
            for card in community_cards: #removing the current community cards from the deck
                deck.cards.remove(card)

        for card in hole_cards: #removing our hole cards from the deck
            deck.cards.remove(card)       
        
        score = 0 

        for _ in range(iters): # MC the probability of winning
            deck.shuffle()

            _COMM = 5 - len(community)
            _OPP = 2 

            draw = deck.peek(_COMM + _OPP)  
            
            opp_hole = draw[:_OPP]
            alt_community = draw[_OPP:]
            
            if community == []:
                our_hand = hole_cards  + alt_community
                opp_hand = opp_hole  + alt_community
            else: 

                our_hand = hole_cards + community_cards + alt_community
                opp_hand = opp_hole + community_cards + alt_community

            our_hand_value = eval7.evaluate(our_hand)
            opp_hand_value = eval7.evaluate(opp_hand)

            if our_hand_value > opp_hand_value:
                score += 2 

            if our_hand_value == opp_hand_value:
                score += 1 

            else: 
                score += 0        

        hand_strength = score/(2*iters) # win probability 

        return hand_strength
    

    def handle_new_round(self, game_state, round_state, active):
        '''
        Called when a new round starts. Called NUM_ROUNDS times.

        Arguments:
        game_state: the GameState object.
        round_state: the RoundState object.
        active: your player's index.

        Returns:
        Nothing.
        '''

        my_bankroll = game_state.bankroll  # the total number of chips you've gained or lost from the beginning of the game to the start of this round
        game_clock = game_state.game_clock  # the total number of seconds your bot has left to play this game
        round_num = game_state.round_num  # the round number from 1 to NUM_ROUNDS
        my_cards = round_state.hands[active]  # your cards
        big_blind = bool(active)  # True if you are the big blind

        self.round_num = round_num


    def handle_round_over(self, game_state, terminal_state, active):
        '''
        Called when a round ends. Called NUM_ROUNDS times.

        Arguments:
        game_state: the GameState object.
        terminal_state: the TerminalState object.
        active: your player's index.

        Returns:
        Nothing.
        '''

        my_delta = terminal_state.deltas[active]  # your bankroll change from this round
        previous_state = terminal_state.previous_state  # RoundState before payoffs
        street = previous_state.street  # 0, 3, 4, or 5 representing when this round ended
        my_cards = previous_state.hands[active]  # your cards
        opp_cards = previous_state.hands[1-active]  # opponent's cards or [] if not revealed

        self.myDelta = my_delta
        self.my_previous_cards = my_cards
        self.opp_prev_cards = opp_cards
        self.prev_end_round = street
        # print(my_delta)
        # print('DELTA: ', self.myDelta)

        if my_delta <= 0: # we lost last turn, reduce risk by raising less each time
            # if self.prevStrength > 0.5 and self.opp_prev_cards == []: #if we had a strong hand and opp folded, we raised too much
            # if self.opp_prev_cards == []:
            if street < 3:                 
                self.raisePreFlopVar = max([0.4, self.raisePreFlopVar - 0.05])
                # print('update pre down')
            else:
                self.raisePostFlopVar = max([0.4, self.raisePostFlopVar - 0.05])
                # print('update post down')

            # self.scaryOffset = min([0.8, self.scaryOffset + 0.01]) #if we lost, we should play more conservatively

        else: # we won last turn, increase risk by raising more each time
            if street < 3:                 
                self.raisePreFlopVar = min([0.6, self.raisePreFlopVar + 0.05])
                # print('update pre up')
            else:
                self.raisePostFlopVar = min([0.8, self.raisePostFlopVar + 0.05])
                # print('update post up')

            # self.scaryOffset =  max([0, self.scaryOffset - 0.01])

        # print("preflopvar, postflopvar, scaryoffset", self.raisePreFlopVar, self.raisePostFlopVar, self.scaryOffset)
    

    def get_action(self, game_state, round_state, active):
        '''
        Where the magic happens - your code should implement this function.
        Called any time the engine needs an action from your bot.

        Arguments:
        game_state: the GameState object.
        round_state: the RoundState object.
        active: your player's index.

        Returns:
        Your action.
        '''

        legal_actions = round_state.legal_actions()  # the actions you are allowed to take
        street = round_state.street  # 0, 3, 4, or 5 representing pre-flop, flop, turn, or river respectively
        my_cards = round_state.hands[active]  # your cards
        board_cards = round_state.deck[:street]  # the board cards
        my_pip = round_state.pips[active]  # the number of chips you have contributed to the pot this round of betting
        opp_pip = round_state.pips[1-active]  # the number of chips your opponent has contributed to the pot this round of betting
        my_stack = round_state.stacks[active]  # the number of chips you have remaining
        opp_stack = round_state.stacks[1-active]  # the number of chips your opponent has remaining
        continue_cost = opp_pip - my_pip  # the number of chips needed to stay in the pot
        my_contribution = STARTING_STACK - my_stack  # the number of chips you have contributed to the pot
        opp_contribution = STARTING_STACK - opp_stack  # the number of chips your opponent has contributed to the pot
        net_upper_raise_bound = round_state.raise_bounds()
        stacks = [my_stack, opp_stack] #keep track of our stacks

        my_action = None

        min_raise, max_raise = round_state.raise_bounds()
        pot_total = my_contribution + opp_contribution

        # raise logic 
        if street <3: #preflop 
            raise_amount = int(my_pip + continue_cost + self.raisePreFlopVar*(pot_total + continue_cost))
        else: #postflop
            raise_amount = int(my_pip + continue_cost + self.raisePostFlopVar*(pot_total + continue_cost))

        # ensure raises are legal
        raise_amount = max([min_raise, raise_amount])
        raise_amount = min([max_raise, raise_amount])

        if (RaiseAction in legal_actions and (raise_amount <= my_stack)):
            temp_action = RaiseAction(raise_amount)
        elif (CallAction in legal_actions and (continue_cost <= my_stack)):
            temp_action = CallAction()
        elif CheckAction in legal_actions:
            temp_action = CheckAction()
        else:
            temp_action = FoldAction() 

        _MONTE_CARLO_ITERS = 100
        
        #running monte carlo simulation when we have community cards vs when we don't 
        if street <3:
            # strength = self.calc_strength(my_cards, _MONTE_CARLO_ITERS)
            # look up strength from precomputed hole cards
            key = self.hole_list_to_key(my_cards)
            strength = self.starting_strengths[key]
        else:
            strength = self.calc_strength(my_cards, _MONTE_CARLO_ITERS, board_cards)

        self.prevStrength = strength

        if continue_cost > 0: 
            _SCARY = 0

            # print("round num: ", self.round_num, "CC/PT: ", continue_cost/pot_total, "strength: ", strength, "continue cost: ", continue_cost)

            if street <3: # if opponent raised early, they are probably more confident
                if continue_cost > 1: #continue cost == 1 is blind
                    if continue_cost/pot_total > 0.1:
                        _SCARY = 0.15
                    if continue_cost/pot_total > 0.3: 
                        _SCARY = 0.25
                    if continue_cost/pot_total > 0.5: 
                        _SCARY = 0.35           
            else: #post flop
                if continue_cost/pot_total > 0.1:
                    _SCARY = 0.1
                if continue_cost/pot_total > 0.3: 
                    _SCARY = 0.2
                if continue_cost/pot_total > 0.5: 
                    _SCARY = 0.3

            _SCARY += self.scaryOffset #this var is adjusted in the handle_round_over function

            strength = max(0, strength - _SCARY)
            pot_odds = continue_cost/(pot_total + continue_cost)

            if strength >= pot_odds: # nonnegative EV decision
                if strength > 0.5 and random.random() < strength: 
                    my_action = temp_action
                else: 
                    my_action = CallAction()
            
            else: #negative EV
                my_action = FoldAction()
                
        else: # continue cost is 0  
            if random.random() < strength: 
                my_action = temp_action
            else: 
                my_action = CheckAction()
            

        return my_action
        

    def hole_list_to_key(self, hole):
                '''
                Converts a hole card list into a key that we can use to query our 
                strength dictionary
                hole: list - A list of two card strings in the engine's format (Kd, As, Th, 7d, etc.)
                '''
                card_1 = hole[0] #get all of our relevant info
                card_2 = hole[1]

                rank_1, suit_1 = card_1[0], card_1[1] #card info
                rank_2, suit_2 = card_2[0], card_2[1]

                numeric_1, numeric_2 = self.rank_to_numeric(rank_1), self.rank_to_numeric(rank_2) #make numeric

                suited = suit_1 == suit_2 #off-suit or not
                suit_string = 's' if suited else 'o'

                if numeric_1 >= numeric_2: #keep our hole cards in rank order
                    return rank_1 + rank_2 + suit_string
                else:
                    return rank_2 + rank_1 + suit_string
        
    def rank_to_numeric(self, rank):
        '''
        Method that converts our given rank as a string
        into an integer ranking
        rank: str - one of 'A, K, Q, J, T, 9, 8, 7, 6, 5, 4, 3, 2'
        '''
        if rank.isnumeric(): #2-9, we can just use the int version of this string
            return int(rank)
        elif rank == 'T': #10 is T, so we need to specify it here
            return 10
        elif rank == 'J': #Face cards for the rest of them
            return 11
        elif rank == 'Q':
            return 12
        elif rank == 'K':
            return 13
        else: #Ace (A) is the only one left, give it the highest rank
            return 14


if __name__ == '__main__':
    run_bot(Player(), parse_args())
