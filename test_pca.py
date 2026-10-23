import math
import random
import unittest
from pca import fit_pca, eigen_symmetric, pca_report


class PCATests(unittest.TestCase):
    def rows(self):
        random.seed(4)
        return [dict(id=i+1,valence=random.uniform(-1,1),direction=random.uniform(-1,1),intensity=random.random()) for i in range(30)]

    def test_scores_centered_components_orthonormal_and_variance(self):
        model=fit_pca(self.rows())
        self.assertIsNone(model['error'])
        self.assertAlmostEqual(sum(model['ratios']),1)
        for i in range(3):
            self.assertAlmostEqual(sum(s[i] for s in model['scores'].values()),0)
            variance=sum(s[i]**2 for s in model['scores'].values())/(model['count']-1)
            self.assertAlmostEqual(variance,model['eigenvalues'][i])
            for j in range(3):
                self.assertAlmostEqual(sum(a*b for a,b in zip(model['components'][i],model['components'][j])),float(i==j))

    def test_complete_reconstruction(self):
        rows=self.rows();model=fit_pca(rows)
        for row in rows:
            score=model['scores'][row['id']]
            for k,feature in enumerate(model['features']):
                z=sum(score[j]*model['components'][j][k] for j in range(3))
                restored=z*model['scales'][k]+model['means'][k]
                self.assertAlmostEqual(restored,row[feature])

    def test_correlated_features_and_constant(self):
        model=fit_pca([dict(id=i,valence=i,direction=-i,intensity=.5) for i in range(5)])
        self.assertAlmostEqual(model['ratios'][0],1)
        self.assertEqual(model['constant_features'],['intensity'])
        self.assertAlmostEqual(model['components'][0][0],-model['components'][0][1])

    def test_unknown_direction_not_imputed(self):
        rows=self.rows();rows[0]['direction']=None
        model=fit_pca(rows)
        self.assertEqual(model['excluded'],1)
        self.assertNotIn(1,model['scores'])

    def test_insufficient_and_zero_variance(self):
        self.assertIsNotNone(fit_pca(self.rows()[:2])['error'])
        self.assertIsNotNone(fit_pca([dict(id=i,valence=0,direction=0,intensity=0) for i in range(3)])['error'])

    def test_order_independence_and_report(self):
        rows=self.rows()
        self.assertEqual(fit_pca(rows),fit_pca(list(reversed(rows))))
        self.assertIn('PC1 + PC2 retain',pca_report(fit_pca(rows)))

    def test_against_numpy_reference_when_available(self):
        try:import numpy as np
        except ImportError:self.skipTest('Optional independent numerical reference unavailable')
        rows=self.rows();model=fit_pca(rows)
        a=np.array([[r[k] for k in model['features']] for r in rows])
        z=(a-a.mean(axis=0))/a.std(axis=0,ddof=1)
        _,singular,_=np.linalg.svd(z,full_matrices=False)
        np.testing.assert_allclose(model['eigenvalues'],singular**2/(len(rows)-1),atol=1e-10)

if __name__=='__main__':unittest.main()
