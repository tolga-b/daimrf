import Image
import matplotlib.pyplot as plt
import numpy as np
from time import time

from daicrf import mrf

from IPython.core.debugger import Tracer
tracer = Tracer()


def stereo_unaries(img1, img2):
    differences = []
    max_disp = 8
    for disp in np.arange(max_disp):
        if disp == 0:
            diff = np.sum((img1 - img2) ** 2, axis=2)
        else:
            diff = np.sum((img1[:, 2 * disp:, :]
                           - img2[:, :-2 * disp, :]) ** 2,
                          axis=2)
        if disp != max_disp - 1:
            diff = diff[:, max_disp - disp - 1:disp - max_disp + 1]
        differences.append(diff)
    return np.dstack(differences).copy("C")


def energy(x, y, pairwise):
    # x is unaries
    # y is a labeling
    n_states = pairwise.shape[0]
    ## unary features:
    gx, gy = np.ogrid[:x.shape[0], :x.shape[1]]
    selected_unaries = x[gx, gy, y]
    unaries_acc = np.sum(x[gx, gy, y])
    unaries_acc = np.bincount(y.ravel(), selected_unaries.ravel(),
                              minlength=n_states)

    ##accumulated pairwise
    #make one hot encoding
    labels = np.zeros((y.shape[0], y.shape[1], n_states),
                      dtype=np.int)
    gx, gy = np.ogrid[:y.shape[0], :y.shape[1]]
    labels[gx, gy, y] = 1
    # vertical edges
    vert = np.dot(labels[1:, :, :].reshape(-1, n_states).T,
                  labels[:-1, :, :].reshape(-1, n_states))
    # horizontal edges
    horz = np.dot(labels[:, 1:, :].reshape(-1, n_states).T,
                  labels[:, :-1, :].reshape(-1, n_states))
    pw = vert + horz
    pw = pw + pw.T - np.diag(np.diag(pw))
    energy = np.dot(np.tril(pw).ravel(), pairwise.ravel()) + unaries_acc.sum()
    return energy


def example():
    img1 = np.asarray(Image.open("scene1.row3.col1.ppm")) / 255.
    img2 = np.asarray(Image.open("scene1.row3.col2.ppm")) / 255.
    img1 = img1[180:220, 80:120]
    img2 = img2[180:220, 80:120]
    unaries = (stereo_unaries(img1, img2) * 100).astype(np.int32)
    n_disps = unaries.shape[2]

    pairwise = .10 * np.eye(n_disps)
    newshape = unaries.shape[:2]

    x, y = np.ogrid[:n_disps, :n_disps]
    #one_d_topology = 5 * np.abs(x - y).astype(np.int32).copy("C")

    # libdai works in exp space
    pairwise_exp = np.exp(pairwise)
    
    # build edges for max product inference:
    inds = np.arange(np.prod(newshape)).reshape(newshape).astype(np.int64)
    horz = np.c_[inds[:, :-1].ravel(), inds[:, 1:].ravel()]
    vert = np.c_[inds[:-1, :].ravel(), inds[1:, :].ravel()]
    edges = np.vstack([horz, vert]).copy()
    pairwise_exp = np.repeat(pairwise_exp[np.newaxis, :, :], len(edges), axis=0)
    #asdf = np.random.permutation(len(edges))
    #edges = edges[asdf]

    start = time()
    max_product = mrf(np.exp(-unaries.reshape(-1, n_disps)),
                      edges, pairwise_exp, alg='maxprod')
    time_maxprod = time() - start
    energy_max_prod = energy(unaries, max_product.reshape(newshape), -pairwise)
    
    start = time()
    trw = mrf(np.exp(-unaries.reshape(-1, n_disps)),
              edges, pairwise_exp, alg='trw')
    time_trw = time() - start
    energy_trw = energy(unaries, trw.reshape(newshape), -pairwise)
    
    start = time()
    treeep = mrf(np.exp(-unaries.reshape(-1, n_disps)),
                 edges, pairwise_exp, alg='treeep')
    time_treeep = time() - start
    energy_treeep = energy(unaries, treeep.reshape(newshape), -pairwise)

    start = time()
    gibbs = mrf(np.exp(-unaries.reshape(-1, n_disps)),
                edges, pairwise_exp, alg='gibbs')
    time_gibbs = time() - start
    energy_gibbs = energy(unaries, gibbs.reshape(newshape), -pairwise)

    fix, axes = plt.subplots(3, 3, figsize=(16, 8))
    energy_argmax = energy(unaries, np.argmin(unaries, axis=2), -pairwise)

    #energies = np.array([energy_argmax, energy_gibbs, energy_max_prod,
                         #energy_treeep, energy_trw])
    #(energy_argmax, energy_gibbs, energy_qpbo,
     #energy_max_prod, energy_treep, energy_trw) = energies - energy_gc

    axes[0, 0].imshow(img1)
    axes[0, 1].imshow(img2)
    axes[0, 2].set_title("unaries only e=%f" % (energy_argmax))
    axes[0, 2].matshow(np.argmin(unaries, axis=2), vmin=0, vmax=8)
    axes[1, 0].set_title("treeep %.2fs, e=%f" % (time_treeep, energy_treeep))
    axes[1, 0].matshow(treeep.reshape(newshape), vmin=0, vmax=8)
    axes[1, 2].set_title("max-product %.2fs, e=%f"
                         % (time_maxprod, energy_max_prod))
    axes[1, 2].matshow(max_product.reshape(newshape), vmin=0, vmax=8)
    axes[2, 0].set_title("trw %.2fs, e=%f" % (time_trw, energy_trw))
    axes[2, 0].matshow(trw.reshape(newshape), vmin=0, vmax=8)
    axes[2, 2].set_title("gibbs %.2fs, e=%f" % (time_gibbs, energy_gibbs))
    axes[2, 2].matshow(gibbs.reshape(newshape), vmin=0, vmax=8)
    for ax in axes.ravel():
            ax.set_xticks(())
            ax.set_yticks(())
    axes[1, 1].axis('off')
    axes[2, 1].axis('off')
    plt.tight_layout()
    plt.show()

example()