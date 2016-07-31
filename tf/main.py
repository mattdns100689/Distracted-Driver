from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import numpy as np
import tensorflow as tf
from nn import Convolution2D, MaxPooling2D
from nn import FullConnected, ReadOutLayer
#import matplotlib.pyplot as plt
from loadData import *
#from matplotlib import cm
import pdb 

chkpt_file = 'checkPoint.ckpt'


def batch_norm(x, n_out, phase_train):
    """
    Batch normalization on convolutional maps.
    Ref.: http://stackoverflow.com/questions/33949786/how-could-i-use-batch-normalization-in-tensorflow
    Args:
        x:           Tensor, 4D BHWD input maps
        n_out:       integer, depth of input maps
        phase_train: boolean tf.Varialbe, true indicates training phase
        scope:       string, variable scope
    Return:
        normed:      batch-normalized maps
    """
    with tf.variable_scope('bn'):
        beta = tf.Variable(tf.constant(0.0, shape=[n_out]),
                                     name='beta', trainable=True)
        gamma = tf.Variable(tf.constant(1.0, shape=[n_out]),
                                      name='gamma', trainable=True)
        batch_mean, batch_var = tf.nn.moments(x, [0,1,2], name='moments')
        ema = tf.train.ExponentialMovingAverage(decay=0.5)

        def mean_var_with_update():
            ema_apply_op = ema.apply([batch_mean, batch_var])
            with tf.control_dependencies([ema_apply_op]):
                return tf.identity(batch_mean), tf.identity(batch_var)

        mean, var = tf.cond(phase_train,
                            mean_var_with_update,
                            lambda: (ema.average(batch_mean), ema.average(batch_var)))
        normed = tf.nn.batch_normalization(x, mean, var, beta, gamma, 1e-3)
    return normed
#

def training(loss, learning_rate):
    optimizer = tf.train.AdamOptimizer(learning_rate)
    # Create a variable to track the global step.
    global_step = tf.Variable(0, name='global_step', trainable=False)
    train_op = optimizer.minimize(loss, global_step=global_step)
    
    return train_op

def evaluation(y_pred, y):
    correct = tf.equal(tf.argmax(y_pred, 1), tf.argmax(y, 1))
    accuracy = tf.reduce_mean(tf.cast(correct, tf.float32))
    
    return accuracy

def mlogloss(predicted, actual):
    '''
      args.
         predicted : predicted probability
                    (sum of predicted proba should be 1.0)
         actual    : actual value, label
    '''
    def inner_fn(item):
        eps = 1.e-15
        item1 = min(item, (1 - eps))
        item1 = max(item, eps)
        res = np.log(item1)

        return res
    
    nrow = actual.shape[0]
    ncol = actual.shape[1]

    mysum = sum([actual[i, j] * inner_fn(predicted[i, j]) 
        for i in range(nrow) for j in range(ncol)])
    
    ans = -1 * mysum / nrow
    
    return ans
#

# Create the model
def inference(x, y_, keep_prob, phase_train):
    x_image = tf.reshape(x, [-1, 60, 40, 3])
    
    with tf.variable_scope('conv_1'):
        conv1 = Convolution2D(x, (60, 40), 3, 32, (3, 3), activation='none')
        conv1_bn = batch_norm(conv1.output(), 32, phase_train)
        conv1_out = tf.nn.relu(conv1_bn)
           
        pool1 = MaxPooling2D(conv1_out)
        pool1_out = pool1.output()
    
    with tf.variable_scope('conv_2'):
        conv2 = Convolution2D(pool1_out, (30, 20), 32, 48, (3, 3), 
                                                          activation='none')
        conv2_bn = batch_norm(conv2.output(), 48, phase_train)
        conv2_out = tf.nn.relu(conv2_bn)
           
        pool2 = MaxPooling2D(conv2_out)
        pool2_out = pool2.output()    

    with tf.variable_scope('conv_3'):
        conv3 = Convolution2D(pool2_out, (15, 10), 48, 64 , (3, 3), 
                                                          activation='none')
        conv3_bn = batch_norm(conv3.output(), 64, phase_train)
        conv3_out = tf.nn.relu(conv3_bn)
           
        pool3 = MaxPooling2D(conv3_out)
        pool3_out = pool3.output()    

    with tf.variable_scope('conv_4'):
        conv4 = Convolution2D(pool3_out, (8, 5), 64, 64 , (3, 3), 
                                                          activation='none')
        conv4_bn = batch_norm(conv4.output(), 64, phase_train)
        conv4_out = tf.nn.relu(conv4_bn)
           
        pool4 = MaxPooling2D(conv4_out)
        pool4_out = pool4.output()    
        pool4_flat = tf.reshape(pool4_out, [-1, 4*3*64])
    
    with tf.variable_scope('fc1'):
        fc1 = FullConnected(pool4_flat, 4*3*64, 100)
        fc1_out = fc1.output()
        fc1_dropped = tf.nn.dropout(fc1_out, keep_prob)
    
    y_pred = ReadOutLayer(fc1_dropped, 100, 10).output()
    
    cross_entropy = tf.reduce_mean(-tf.reduce_sum(y_ * tf.log(y_pred), 
                                    reduction_indices=[1]))
    loss = cross_entropy
    train_step = training(loss, 0.001)
    accuracy = evaluation(y_pred, y_)
    
    return loss, accuracy, y_pred
 
#
if __name__ == '__main__':
    TASK = 'train'    # 'train' or 'test'

    batchSize = 10
    w,h,c = 60,40,3
    epochs = range(10)
    lr = 0.0001
    
    # Variables
    x = tf.placeholder(tf.float32, [None, w, h, c])
    y_ = tf.placeholder(tf.float32, [None, 10])
    keep_prob = tf.placeholder(tf.float32)
    phase_train = tf.placeholder(tf.bool, name='phase_train')
    
    loss, accuracy, y_pred = inference(x, y_, 
                                         keep_prob, phase_train)

    # Train

    train_step = tf.train.AdagradOptimizer(lr).minimize(loss)
    vars_to_train = tf.trainable_variables()    # option-1
    vars_for_bn1 = tf.get_collection(tf.GraphKeys.VARIABLES, scope='conv_1/bn')
    vars_for_bn2 = tf.get_collection(tf.GraphKeys.VARIABLES, scope='conv_2/bn')
    vars_to_train = list(set(vars_to_train).union(set(vars_for_bn1)))
    vars_to_train = list(set(vars_to_train).union(set(vars_for_bn2)))
    
    if TASK == 'test' or os.path.exists(chkpt_file):
        restore_call = True
        vars_all = tf.all_variables()
        vars_to_init = list(set(vars_all) - set(vars_to_train))
        init = tf.initialize_variables(vars_to_init)
    elif TASK == 'train':
        restore_call = False
        init = tf.initialize_all_variables()
    else:
        print('Check task switch.')
          
    saver = tf.train.Saver(vars_to_train)     # option-1
    # saver = tf.train.Saver()                   # option-2
    

    with tf.Session() as sess:
        # if TASK == 'train':              # add in option-2 case
        sess.run(init)                     # option-1
               
        if restore_call:
            # Restore variables from disk.
            saver.restore(sess, chkpt_file) 


        dataLoad = dataLoader(width = w, height = h, channels = c)
        train = dataLoad.getBatch("train",batchSize=batchSize)
        test = dataLoad.getBatch("test",batchSize=batchSize)

        if TASK == 'train':
            for i in epochs:
                print('\n Training epoch number %d ...' % i)
                dataLoad.finished = False         
                while dataLoad.finished == False:
                    batch_xs, batch_ys = train.next()

                    #pdb.set_trace()
                    train_step.run({x: batch_xs, y_: batch_ys, keep_prob: 0.5,
                          phase_train: True})
                    if dataLoad.batchIdxTrain % 100 == 0:
                        cv_fd = {x: batch_xs, y_: batch_ys, keep_prob: 1.0, 
                                                       phase_train: False}
                        train_loss = loss.eval(cv_fd)
                        train_accuracy = accuracy.eval(cv_fd)
                        
                        print('  step, loss, accurary = %6d: %10.6f, %10.6f' % (dataLoad.batchIdxTrain, 
                            train_loss, train_accuracy))
                
                print('\n Testing epoch number %d ...' % i)
                dataLoad.finished = False         
                while dataLoad.finished == False:
                    batch_xs, batch_ys = test.next()

                    # Test trained model
                    test_fd = {x: batch_xs, y_: batch_ys, 
                            keep_prob: 1.0, phase_train: False}
                    print(' accuracy = %10.6f' % accuracy.eval(test_fd))
                    # Multiclass Log Loss
                    pred = y_pred.eval(test_fd)
                    print(' multiclass logloss = %10.6f' % mlogloss(pred, batch_ys))
    
        # Save the variables to disk.
        def save():
            if TASK == 'train':
                save_path = saver.save(sess, chkpt_file)
                print("Model saved in file: %s" % save_path)
    