from functools import lru_cache
from collections import OrderedDict


class Event:
    """
    Simple event with a name and (optionally) some data.
    """
    def __init__(self, name: str, data: dict=None):
        self.name = name
        self.data = data

    def __eq__(self, other):
        return isinstance(other, Event) and self.name == other.name

    def __hash__(self):
        return hash(self.name)

    def to_dict(self):
        return OrderedDict({'name': self.name})


class State:
    """
    State element with a name.
    """

    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, self.name)

    def __eq__(self, other):
        return isinstance(other, State) and self.name == other.name

    def __hash__(self):
        return hash(self.name)

    def to_dict(self) -> dict:
        return {'name': self.name}


class ActionStateMixin:
    """
    State that can define actions on entry and on exit.
    """
    def __init__(self, on_entry: str=None, on_exit: str=None):
        self.on_entry = on_entry
        self.on_exit = on_exit

    def to_dict(self) -> dict:
        d = {}
        if self.on_entry:
            d['on_entry'] = self.on_entry
        if self.on_exit:
            d['on_exit'] = self.on_exit
        return d


class TransitionStateMixin:
    """
    A simple state can host transitions
    """

    def __init__(self):
        self.transitions = []

    def add_transition(self, transition):
        """
        :param transition: an instance of Transition
        """
        self.transitions.append(transition)

    def to_dict(self) -> dict:
        d = {}
        if len(self.transitions) > 0:
            d['transitions'] = [transition.to_dict() for transition in self.transitions]
        return d


class CompositeStateMixin:
    """
    Composite state can have children states.
    """
    def __init__(self):
        self.children = []

    def add_child(self, state_name):
        self.children.append(state_name)

    def to_dict(self) -> dict:
        return {'states': self.children}


class BasicState(State, TransitionStateMixin, ActionStateMixin):
    """
    A basic state, with a name, transitions, actions, etc. but no children.
    """
    def __init__(self, name: str, on_entry: str=None, on_exit: str=None):
        State.__init__(self, name)
        TransitionStateMixin.__init__(self)
        ActionStateMixin.__init__(self, on_entry, on_exit)

    def to_dict(self) -> dict:
        d = State.to_dict(self)
        d.update(ActionStateMixin.to_dict(self))
        d.update(TransitionStateMixin.to_dict(self))
        return d


class CompoundState(State, TransitionStateMixin, ActionStateMixin, CompositeStateMixin):
    """
    Compound states must have children states.
    """
    def __init__(self, name: str, initial: str, on_entry: str=None, on_exit: str=None):
        State.__init__(self, name)
        TransitionStateMixin.__init__(self)
        ActionStateMixin.__init__(self, on_entry, on_exit)
        CompositeStateMixin.__init__(self)
        self.initial = initial

    def to_dict(self) -> dict:
        d = State.to_dict(self)
        d['initial'] = self.initial
        d.update(ActionStateMixin.to_dict(self))
        d.update(TransitionStateMixin.to_dict(self))
        d.update(CompositeStateMixin.to_dict(self))
        return d


class OrthogonalState(State, TransitionStateMixin, ActionStateMixin, CompositeStateMixin):
    """
    Orthogonal states run their children simultaneously.
    """
    def __init__(self, name: str, on_entry: str=None, on_exit: str=None):
        State.__init__(self, name)
        TransitionStateMixin.__init__(self)
        ActionStateMixin.__init__(self, on_entry, on_exit)
        CompositeStateMixin.__init__(self)

    def to_dict(self) -> dict:
        d = State.to_dict(self)
        d['orthogonal'] = True
        d.update(ActionStateMixin.to_dict(self))
        d.update(TransitionStateMixin.to_dict(self))
        d.update(CompositeStateMixin.to_dict(self))
        return d


class HistoryState(State):
    """
    History state can be either 'shallow' (default) or 'deep'.
    A shallow history state resumes the execution of its parent.
    A deep history state resumes the execution of its parent, and resume
    every (recursively) parent's substate execution.
    """

    def __init__(self, name: str, initial: str=None, deep: bool=False):
        State.__init__(self, name)
        self.name = name
        self.memory = [initial]
        self.initial = initial
        self.deep = deep

    def to_dict(self):
        d = State.to_dict(self)
        d['type'] = 'history'
        if self.initial:
            d['initial'] = self.initial
        if self.deep:
            d['deep'] = True
        return d


class FinalState(State, ActionStateMixin):
    """
    Final state has NO transition and is used to detect state machine termination.
    """

    def __init__(self, name: str, on_entry: str=None, on_exit: str=None):
        State.__init__(self, name)
        ActionStateMixin.__init__(self, on_entry, on_exit)

    def to_dict(self):
        d = State.to_dict(self)
        d['type'] = 'final'
        d.update(ActionStateMixin.to_dict(self))
        return d


class Transition(object):
    """
    A Transition between two states.
    Transition can be eventless or internal (but not both at once).
    A condition (code as string) can be specified as a guard.
    """

    def __init__(self, from_state: str, to_state: str=None, event: Event=None, condition: str=None, action: str=None):
        if to_state is None and event is None:
            raise ValueError('You should either specify to_state or event.')
        self.from_state = from_state
        self.to_state = to_state
        self.event = event
        self.condition = condition
        self.action = action

    @property
    def internal(self):
        return self.to_state is None

    @property
    def eventless(self):
        return self.event is None

    def __repr__(self):
        return 'Transition({}, {}, {})'.format(self.from_state, self.to_state, self.event)

    def to_dict(self):
        d = OrderedDict()
        if not self.internal:
            d['target'] = self.to_state
        if not self.eventless:
            d['event'] = self.event.to_dict()
        if self.condition:
            d['condition'] = self.condition
        if self.action:
            d['action'] = self.action
        return d


class StateMachine(object):
    def __init__(self, name: str, initial: str, execute: str=None):
        self.name = name
        self.initial = initial
        self.execute = execute  # code that should be executed on start
        self.states = OrderedDict()  # name -> State object
        self.transitions = []  # list of Transition objects
        self.parent = OrderedDict()  # name -> parent.name
        self.children = []

    def register_state(self, state: State, parent: str):
        """
        Register given state in current state machine and register it to its parent
        :param state: instance of State to add
        :param parent: name of parent state
        """
        self.states[state.name] = state
        self.parent[state.name] = parent.name if isinstance(parent, State) else parent

        # Register on parent state
        parent_state = self.states.get(self.parent[state.name], None)
        if parent_state is not None:
            self.states[self.parent[state.name]].add_child(state.name)
        else:
            # ... or on top-level state (self!)
            self.children.append(state.name)

    def register_transition(self, transition: Transition):
        """
        Register given transition in current state machine and register it on the source state
        :param transition: instance of Transition
        """
        self.transitions.append(transition)
        self.states[transition.from_state].add_transition(transition)

    def __repr__(self):
        return 'State machine: {}'.format(self.name)

    @lru_cache()
    def ancestors_for(self, state: str) -> list:
        """
        :param state: name of the state
        :return: ancestors, in decreasing depth
        """
        ancestors = []
        parent = self.parent[state]
        while parent:
            ancestors.append(parent)
            parent = self.parent[parent]
        return ancestors

    @lru_cache()
    def descendants_for(self, state: str) -> list:
        """
        :param state: name of the state
        :return: descendants, in increasing depth
        """
        descendants = []
        states_to_consider = [state]
        while states_to_consider:
            state = states_to_consider.pop(0)
            # Get children for composite state
            for child in getattr(self.states[state], 'children', []):
                states_to_consider.append(child)
                descendants.append(child)
        return descendants

    @lru_cache()
    def depth_of(self, state: str) -> int:
        """
        Return the depth of the given state, starting from 0 (root, top-level).
        :param state: name of the state
        :return: depth of state
        """
        if state is None:
            return 0
        ancestors = self.ancestors_for(state)
        return len(ancestors) + 1

    @lru_cache()
    def least_common_ancestor(self, s1: str, s2: str) -> str:
        """
        Return the deepest common ancestor for s1 and s2, or None if
        there is no common ancestor except root (top-level) state.
        :param s1: name of first state
        :param s2: name of second state
        :return: name of deepest common ancestor or None
        """
        s1_anc = self.ancestors_for(s1)
        s2_anc = self.ancestors_for(s2)
        for state in s1_anc:
            if state in s2_anc:
                return state

    def leaf_for(self, states: list) -> list:
        """
        Return a subset of `states` that are leaves, ie. return each state from
        `states` that has no descendant in `states`.
        :param states: A list of state names
        :return: A list of state names
        """
        leaves = []
        # TODO: Need a more efficient way to compute this set
        for state in states:
            keep = True
            for descendant in self.descendants_for(state):
                if descendant in states:
                    keep = False
                    break
            if keep:
                leaves.append(state)
        return leaves

    def to_dict(self) -> dict:
        d = OrderedDict()
        d['name'] = self.name
        d['initial'] = self.initial
        d['states'] = self.children

        if self.execute:
            d['execute'] = self.execute

        statelist_to_expand = [d['states']]
        while statelist_to_expand:
            statelist = statelist_to_expand.pop()
            for i, state in enumerate(statelist):
                statelist[i] = self.states[state].to_dict()
                new_statelist = statelist[i].get('states', [])
                if len(new_statelist) > 0:
                    statelist_to_expand.append(new_statelist)
        return {'statemachine': d}
