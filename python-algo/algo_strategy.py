import gamelib
import random
import math
import warnings
from sys import maxsize
import json
import sys

"""
They capture stdout, so we have a custom print that uses stderr
"""
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips: 

  - You can analyze action frames by modifying on_action_frame function

  - The GameState.map object can be manually manipulated to create hypothetical 
  board states. Though, we recommended making a copy of the map to preserve 
  the actual current map state.
"""

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))
        # This is a priority-sorted list of where we want to have filters
        self.destructor_goals = [[3, 12], [24, 12], [13, 3], [14, 3]]
        # Diagonal defense line
        self.filter_goals = [[5,11], [22,11], [6,10], [21,10], [7,9], [20,9], [8,8], [19,8], [9,7], [18,7], [10,6], [17,6]]

    def on_game_start(self, config):
        """ 
        Read in config and perform any initial setup here 
        """
        gamelib.debug_write('Configuring your custom algo strategy...')
        self.config = config
        global FILTER, ENCRYPTOR, DESTRUCTOR, PING, EMP, SCRAMBLER, BITS, CORES
        FILTER = config["unitInformation"][0]["shorthand"]
        ENCRYPTOR = config["unitInformation"][1]["shorthand"]
        DESTRUCTOR = config["unitInformation"][2]["shorthand"]
        PING = config["unitInformation"][3]["shorthand"]
        EMP = config["unitInformation"][4]["shorthand"]
        SCRAMBLER = config["unitInformation"][5]["shorthand"]
        BITS = 1
        CORES = 0
        # This is a good place to do initial setup
        self.setup_complete = False
        self.scored_on_locations = []
        self.our_spawns = []
        self.our_locations = []
        self.init_our_locations()


    def init_our_locations(self):
        our_locations = []
        min_x = 13
        max_x = 14
        for y in range(0, 14):
            self.our_spawns.append((min_x, y))
            self.our_spawns.append((max_x, y))
            for x in range(min_x, max_x + 1):
                self.our_locations.append((x, y))
            min_x -= 1
            max_x += 1

    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        game_state.suppress_warnings(True)  #Comment or remove this line to enable warnings.

        if not self.setup_complete:
            self.build_initial_defences(game_state)
            self.setup_complete = True

        self.starter_strategy(game_state)

        game_state.submit_turn()

    """
    Build basic defenses using hardcoded locations. (Only call this once at the start!)
    """
    def build_initial_defences(self, gs):
        gs.attempt_spawn(DESTRUCTOR, self.destructor_goals)

    """
    Build as much as possible in priority order while cores are available
    """
    def build_reactive_defense(self, gs):
        # FIXME: If we've lost destructors, things are bad - maybe consider strategy change
        gs.attempt_spawn(DESTRUCTOR, self.destructor_goals)
        # We do this one-by one since we never want to place a filter that we don't upgrade
        for f in self.filter_goals:
            # We only create a filter if we can also upgrade it
            if gs.get_resource(CORES) < 2:
                return
            gs.attempt_spawn(FILTER, [f])
            gs.attempt_upgrade([f])
        # If we still have bits left, upgrade the destructors (we already made
        # sure they all existed earlier)
        # TODO: Only do this if they have encryptors
        gs.attempt_upgrade(self.destructor_goals)

    """
    NOTE: All the methods after this point are part of the sample starter-algo
    strategy and can safely be replaced for your custom algo.
    """

    def starter_strategy(self, game_state):
        """
        For defense we will use a spread out layout and some Scramblers early on.
        We will place destructors near locations the opponent managed to score on.
        For offense we will use long range EMPs if they place stationary units near the enemy's front.
        If there are no stationary units to attack in the front, we will send Pings to try and score quickly.
        """
        # Now build reactive defenses based on where the enemy scored
        self.build_reactive_defense(game_state)

        # Fixme: Add scramblers on first turn
        if game_state.turn_number == 0:
            pass
        else:
            spammed_pings = self.spam_pings_if_good(game_state)
            # Fixme: Might want to use another strategy if pings were not deployaed
            if not spammed_pings:
                pass

        # Lastly, if we have spare cores, let's build some Encryptors to boost our Pings' health.
        # encryptor_locations = [[13, 2], [14, 2], [13, 3], [14, 3]]
        # game_state.attempt_spawn(ENCRYPTOR, encryptor_locations)

    def stall_with_scramblers(self, game_state):
        """
        Send out Scramblers at random locations to defend our base from enemy moving units.
        """
        # We can spawn moving units on our edges so a list of all our edge locations
        friendly_edges = game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_LEFT) + game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_RIGHT)
        
        # Remove locations that are blocked by our own firewalls 
        # since we can't deploy units there.
        deploy_locations = self.filter_blocked_locations(friendly_edges, game_state)
        
        # While we have remaining bits to spend lets send out scramblers randomly.
        while game_state.get_resource(BITS) >= game_state.type_cost(SCRAMBLER)[BITS] and len(deploy_locations) > 0:
            # Choose a random deploy location.
            deploy_index = random.randint(0, len(deploy_locations) - 1)
            deploy_location = deploy_locations[deploy_index]
            
            game_state.attempt_spawn(SCRAMBLER, deploy_location)
            """
            We don't have to remove the location since multiple information 
            units can occupy the same space.
            """

    def spam_pings_if_good(self, game_state):
        """
        Places num_ping pings at a fixed location if it would be effective
        """

        max_num_pings = game_state.BITS
        eprint("Num pings: ", max_num_pings)
        max_health = 15 * max_num_pings
        valid_placements = [position for position in self.our_locations if game_state.can_spawn(PING, position, max_num_pings)]
        # assert len(valid_placements) > 0
        potential_damages = self.location_to_damages(game_state, valid_placements)
        good_indices = []
        for i in range(len(valid_placements)):
            if spawn_attacker_threshold(max_health, potential_damages[i]) or max_num_pings >= 10:
                good_indices.append(i)
        # Only spawn Pings if we determine they are good enough as per spawn_attacker_threshold
        if good_indices:
            ind = random.choice(good_indices)
            deploy_location = valid_placements[ind]
            assert game_state.can_spawn(PING, deploy_location, max_num_pings)
            game_state.attempt_spawn(PING, location, max_num_pings)
            return True
        else:
            return False
    
    def spawn_attacker_threshold(self, health, damage_taken):
        return health >= 1.5 * damage_taken

    def emp_line_strategy(self, game_state):
        """
        Build a line of the cheapest stationary unit so our EMP's can attack from long range.
        """
        # First let's figure out the cheapest unit
        # We could just check the game rules, but this demonstrates how to use the GameUnit class
        stationary_units = [FILTER, DESTRUCTOR, ENCRYPTOR]
        cheapest_unit = FILTER
        for unit in stationary_units:
            unit_class = gamelib.GameUnit(unit, game_state.config)
            if unit_class.cost[game_state.BITS] < gamelib.GameUnit(cheapest_unit, game_state.config).cost[game_state.BITS]:
                cheapest_unit = unit

        # Now let's build out a line of stationary units. This will prevent our EMPs from running into the enemy base.
        # Instead they will stay at the perfect distance to attack the front two rows of the enemy base.
        for x in range(27, 5, -1):
            game_state.attempt_spawn(cheapest_unit, [x, 11])

        # Now spawn EMPs next to the line
        # By asking attempt_spawn to spawn 1000 units, it will essentially spawn as many as we have resources for
        game_state.attempt_spawn(EMP, [24, 10], 1000)

    def least_damage_spawn_location(self, game_state, location_options):
        """
        This function will help us guess which location is the safest to spawn moving units from.
        It gets the path the unit will take then checks locations on that path to 
        estimate the path's damage risk.
        """
        damages = []
        # Get the damage estimate each path will take
        for location in location_options:
            path = game_state.find_path_to_edge(location)
            damage = 0
            for path_location in path:
                # Get number of enemy destructors that can attack the final location and multiply by destructor damage
                damage += len(game_state.get_attackers(path_location, 0)) * gamelib.GameUnit(DESTRUCTOR, game_state.config).damage_i
            damages.append(damage)
        
        # Now just return the location that takes the least damage
        return location_options[damages.index(min(damages))]

    def location_to_damages(self, game_state, location_options):
        """
        This function gives us a list of estimated damages taken when spawning a unit at each location, 
        the damages are ordered in the same order that locations are in location_options
        """
        damages = []
        # Get the damage estimate each path will take
        for location in location_options:
            path = game_state.find_path_to_edge(location)
            damage = 0
            for path_location in path:
                # Get number of enemy destructors that can attack the final location and multiply by destructor damage
                damage += len(game_state.get_attackers(path_location, 0)) * gamelib.GameUnit(DESTRUCTOR, game_state.config).damage_i
            damages.append(damage)
        
        return damages

    def detect_enemy_unit(self, game_state, unit_type=None, valid_x = None, valid_y = None):
        total_units = 0
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 1 and (unit_type is None or unit.unit_type == unit_type) and (valid_x is None or location[0] in valid_x) and (valid_y is None or location[1] in valid_y):
                        total_units += 1
        return total_units
        
    def filter_blocked_locations(self, locations, game_state):
        filtered = []
        for location in locations:
            if not game_state.contains_stationary_unit(location):
                filtered.append(location)
        return filtered

    def on_action_frame(self, turn_string):
        """
        This is the action frame of the game. This function could be called 
        hundreds of times per turn and could slow the algo down so avoid putting slow code here.
        Processing the action frames is complicated so we only suggest it if you have time and experience.
        Full doc on format of a game frame at: https://docs.c1games.com/json-docs.html
        """
        # Let's record at what position we get scored on
        state = json.loads(turn_string)
        events = state["events"]
        breaches = events["breach"]
        for breach in breaches:
            location = breach[0]
            unit_owner_self = True if breach[4] == 1 else False
            # When parsing the frame data directly, 
            # 1 is integer for yourself, 2 is opponent (StarterKit code uses 0, 1 as player_index instead)
            if not unit_owner_self:
                gamelib.debug_write("Got scored on at: {}".format(location))
                self.scored_on_locations.append(location)
                gamelib.debug_write("All locations: {}".format(self.scored_on_locations))


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
