import numpy as np
import tensorflow as tf
import tensorflow_probability as tfp
from tensorflow.keras.layers import Dense


class CategoricalActor(tf.keras.Model):
    def __init__(self, state_shape, action_dim, units=(256, 256),
                 hidden_activation="relu", name="CategoricalActor"):
        super().__init__(name=name)
        self.action_dim = action_dim

        base_layers = []
        for cur_layer_size in units:
            cur_layer = tf.keras.layers.Dense(cur_layer_size, activation=hidden_activation)
            base_layers.append(cur_layer)

        self.base_layers = base_layers
        self.out_prob = Dense(action_dim, activation='softmax')

        self(tf.constant(
            np.zeros(shape=(1,)+state_shape, dtype=np.float32)))

    def _compute_dist(self, states):
        """
        Compute categorical distribution

        :param states (np.ndarray or tf.Tensor): Inputs to neural network.
            NN outputs probabilities of K classes
        :return: Categorical distribution
        """
        features = states

        for cur_layer in self.base_layers:
            features = cur_layer(features)

        probs = self.out_prob(features)
        dist = tfp.distributions.Categorical(probs)

        return dist

    def compute_prob(self, states):
        return self._compute_dist(states)["prob"]

    def call(self, states, test=False):
        """
        Compute actions and log probability of the selected action

        :return action (tf.Tensors): Tensor of actions
        :return log_probs (tf.Tensor): Tensors of log probabilities of selected actions
        """
        dist = self._compute_dist(states)

        if test:
            action = dist.mean()  # (size,)
        else:
            action = dist.sample()  # (size,)
        log_prob = dist.prob(action)

        return action, log_prob

    def compute_entropy(self, states):
        dist = self._compute_dist(states)
        return dist.entropy()

    def compute_log_probs(self, states, actions):
        """Compute log probabilities of inputted actions

        :param states (tf.Tensor): Tensors of inputs to NN
        :param actions (tf.Tensor): Tensors of NOT one-hot vector.
            They will be converted to one-hot vector inside this function.
        """
        param = self._compute_dist(states)
        actions = tf.one_hot(
            indices=tf.squeeze(actions),
            depth=self.action_dim)
        param["prob"] = tf.cond(
            tf.math.greater(tf.rank(actions), tf.rank(param["prob"])),
            lambda: tf.expand_dims(param["prob"], axis=0),
            lambda: param["prob"])
        actions = tf.cond(
            tf.math.greater(tf.rank(param["prob"]), tf.rank(actions)),
            lambda: tf.expand_dims(actions, axis=0),
            lambda: actions)
        log_prob = self.dist.log_likelihood(actions, param)
        return log_prob


class CategoricalActorCritic(CategoricalActor):
    def __init__(self, *args, **kwargs):
        tf.keras.Model.__init__(self)
        self.v = Dense(1, activation="linear")
        super().__init__(*args, **kwargs)

    def call(self, states, test=False):
        features = self._compute_feature(states)
        probs = self.prob(features)
        param = {"prob": probs}
        if test:
            action = tf.math.argmax(param["prob"], axis=1)  # (size,)
        else:
            action = tf.squeeze(self.dist.sample(param), axis=1)  # (size,)

        log_prob = self.dist.log_likelihood(
            tf.one_hot(indices=action, depth=self.action_dim), param)
        v = self.v(features)

        return action, log_prob, v
