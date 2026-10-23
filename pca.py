"""Standardized PCA of the three existing emotional scores; no dependencies."""
import math

FEATURES = ('valence', 'direction', 'intensity')


def eigen_symmetric(matrix):
    """Jacobi eigendecomposition for a real symmetric 3x3 matrix."""
    a = [list(row) for row in matrix]
    v = [[float(i == j) for j in range(3)] for i in range(3)]
    for _ in range(100):
        p, q = max(((0, 1), (0, 2), (1, 2)), key=lambda pair: abs(a[pair[0]][pair[1]]))
        if abs(a[p][q]) < 1e-13:
            break
        angle = .5 * math.atan2(2 * a[p][q], a[q][q] - a[p][p])
        c, s = math.cos(angle), math.sin(angle)
        app, aqq, apq = a[p][p], a[q][q], a[p][q]
        a[p][p] = c*c*app - 2*s*c*apq + s*s*aqq
        a[q][q] = s*s*app + 2*s*c*apq + c*c*aqq
        a[p][q] = a[q][p] = 0.0
        for k in range(3):
            if k != p and k != q:
                akp, akq = a[k][p], a[k][q]
                a[k][p] = a[p][k] = c*akp - s*akq
                a[k][q] = a[q][k] = s*akp + c*akq
            vkp, vkq = v[k][p], v[k][q]
            v[k][p], v[k][q] = c*vkp - s*vkq, s*vkp + c*vkq
    pairs = []
    for j in range(3):
        vector = [v[i][j] for i in range(3)]
        # A deterministic sign convention; signs have no intrinsic emotional meaning.
        largest = max(range(3), key=lambda i: abs(vector[i]))
        if vector[largest] < 0:
            vector = [-x for x in vector]
        pairs.append((max(0.0, a[j][j]), vector))
    return sorted(pairs, key=lambda pair: -pair[0])


def fit_pca(rows):
    ordered = sorted(rows, key=lambda r: r['id'])
    valid = [r for r in ordered if all(type(r.get(k)) in (int,float) and math.isfinite(r[k]) for k in FEATURES)]
    model = {'count': len(valid), 'excluded': len(ordered)-len(valid), 'features': FEATURES,
             'scores': {}, 'error': None, 'ratios': [], 'components': [], 'scale': 1.0}
    if len(valid) < 3:
        model['error'] = 'PCA needs at least 3 analyzed paragraphs with known direction.'
        return model
    n = len(valid)
    means = [sum(r[k] for r in valid)/n for k in FEATURES]
    deviations = [math.sqrt(sum((r[k]-means[j])**2 for r in valid)/(n-1)) for j,k in enumerate(FEATURES)]
    scales = [sd if sd > 1e-12 else 1.0 for sd in deviations]
    z = [[(r[k]-means[j])/scales[j] if deviations[j] > 1e-12 else 0.0 for j,k in enumerate(FEATURES)] for r in valid]
    covariance = [[sum(row[i]*row[j] for row in z)/(n-1) for j in range(3)] for i in range(3)]
    pairs = eigen_symmetric(covariance)
    total = sum(value for value,_ in pairs)
    if total < 1e-12:
        model['error'] = 'All eligible scores are identical; there is no variation for PCA to explain.'
        return model
    components = [vector for _,vector in pairs]
    scores = {r['id']: [sum(x*w for x,w in zip(row,component)) for component in components] for r,row in zip(valid,z)}
    model.update(means=means, scales=scales, constant_features=[FEATURES[i] for i,sd in enumerate(deviations) if sd<=1e-12],
                 components=components, eigenvalues=[value for value,_ in pairs], ratios=[value/total for value,_ in pairs],
                 scores=scores, scale=max(1e-12,max(abs(x) for row in scores.values() for x in row)))
    return model


def pca_report(model):
    if model['error']:
        return model['error']
    lines = [f"Standardized PCA · {model['count']} paragraphs included · {model['excluded']} excluded",
             'Inputs: valence, direction, intensity. Unknown direction is excluded.',
             'Fit uses all eligible results, independent of filters and playback position.',
             'Each feature is centered and divided by its sample standard deviation.',
             'Constant features contribute zero. Component signs are arbitrary.', '',
             'Component     Variation       Weights: valence / direction / intensity']
    for i,(ratio,component) in enumerate(zip(model['ratios'],model['components']),1):
        lines.append(f"PC{i}              {ratio:6.2%}       " + ' / '.join(f'{w:+.4f}' for w in component))
    lines += ['', f"PC1 + PC2 retain {sum(model['ratios'][:2]):.2%} of variance.",
              'PC1–PC3 retain all variance of these three inputs; this is a rotation of standardized scores,',
              'not PCA of text embeddings or a broader emotion vocabulary.', '',
              'Coordinate formula: PCj = sum(weight[j,k] × (feature[k] − mean[k]) / scale[k]).',
              'Means: ' + ', '.join(f'{k}={v:.4f}' for k,v in zip(FEATURES,model['means'])),
              'Scales: ' + ', '.join(f'{k}={v:.4f}' for k,v in zip(FEATURES,model['scales'])),
              'Constant features: ' + (', '.join(model['constant_features']) or 'none'),
              'Near-equal eigenvalues can make individual component directions unstable.',
              'Colors still represent original valence. Display scaling is equal on all axes.']
    return '\n'.join(lines)
