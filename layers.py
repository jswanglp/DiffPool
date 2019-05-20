import numpy as np
import tensorflow as tf
from tensorflow import keras


class GCN(keras.layers.Layer):

    def __init__(self, features, cheb=False, **kwargs):
        self.F_prime = features
        self.cheb = cheb

        self.w = []

        super(GCN, self).__init__(**kwargs)

    def build(self, input_shape):
        # input now is a tuple of tensors (A, X)
        self.w.append(self.add_weight(name="W_0",
                                 shape=(input_shape[1][2], self.F_prime),
                                 initializer=tf.initializers.GlorotUniform(),
                                 trainable=True)
                            )
        if self.cheb:
            self.w.append(self.add_weight(name="W_1",
                                          shape=(input_shape[1][2], self.F_prime),
                                          initializer=tf.initializers.GlorotUniform(),
                                          trainable=True)
                          )

        super(GCN, self).build(input_shape)

    def call(self, x):
        # input is a tuple (A, X)
        filtres = x[0]
        x = x[1]

        # x = tf.cast(x, tf.float64)
        batch_size = x.shape[0]
        in_size = x.shape[1]
        in_weights = x.shape[2]
        out_weights = self.F_prime

        # tf.print(tf.sparse.to_dense(self.A), summarize=-1)

        # tf.print(x, summarize=-1)
        x = tf.reshape(x, [-1, in_weights])
        # tf.print(x, summarize=-1)

        output = []

        for i in range(len(self.w)):
            hidden = tf.matmul(x, self.w[i])

            # self.filtres[i] = self.convert_sparse_matrix_to_sparse_tensor(self.filtres[i])
            hidden = tf.sparse.sparse_dense_matmul(filtres[i], hidden)

            # tf.print(hidden, summarize=-1)
            hidden = tf.reshape(hidden, [-1, in_size, out_weights])
            # tf.print(hidden, summarize=-1)

            output.append(hidden)
        # tf.print(tf.add_n(output), summarize=-1)
        return tf.tuple([filtres, tf.keras.activations.relu(tf.add_n(output))])

    def compute_output_shape(self, input_shape):
        return (input_shape[0], self.F_prime)


class SimplePool(keras.layers.Layer):

    def __init__(self, batch_size, mode, **kwargs):
        assert mode == "max" or mode == "mean", "GCNPool must have 'max' or 'mean' as mode"

        self.batch_size = batch_size
        self.mode = mode

        super(SimplePool, self).__init__(**kwargs)

    def build(self, input_shape):
        self.F_prime = input_shape[2]
        self.in_size = input_shape[1]

        super(SimplePool, self).build(input_shape)

    def call(self, x):
        segment_ids = np.array([], dtype=np.int32).reshape(0, self.in_size)

        for b in range(self.batch_size):
            index = np.repeat(b, self.in_size)
            segment_ids = np.concatenate((segment_ids, index), axis=None)

        # tf.print(x, summarize=-1)
        x = tf.reshape(x, [-1, self.F_prime])
        # tf.print(x, summarize=-1)

        if self.mode == "max":
            x = tf.math.segment_max(x, segment_ids)
        else:
            x = tf.math.segment_mean(x, segment_ids)

        # tf.print(x, summarize=-1)

        return x

    def compute_output_shape(self, input_shape):
        return (input_shape[0] / self.in_size, self.F_prime)


class DiffPool(keras.layers.Layer):

    def __init__(self, A, **kwargs):

        self.A = A

        super(DiffPool, self).__init__(**kwargs)

    def build(self, input_shape):

        self.pool = GCN(self.A, input_shape[2])
        self.embed = GCN(self.A, input_shape[2])

        super(DiffPool, self).build(input_shape)

    def call(self, x):

        S = tf.keras.activations.softmax(self.pool(x), axis = 1)
        Z = self.embed(x)

        coarse_X = tf.matmul(S, Z)

        coarse_A = tf.sparse.sparse_dense_matmul(self.A, S)
        coarse_A = tf.matmul(tf.transpose(S), coarse_A, b_is_sparse=True)

        return (coarse_A, coarse_X)

    def compute_output_shape(self, input_shape):
        return