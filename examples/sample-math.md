# 数学公式专题示例 / Mathematics Formula Examples

## 微积分 / Calculus

### 极限 / Limits

重要极限：

$$\lim_{x \to 0} \frac{\sin x}{x} = 1$$

$$\lim_{x \to \infty} \left(1 + \frac{1}{x}\right)^x = e$$

### 导数公式 / Derivative Formulas

基本导数：

- $(x^n)' = nx^{n-1}$
- $(\sin x)' = \cos x$
- $(\cos x)' = -\sin x$
- $(e^x)' = e^x$
- $(\ln x)' = \frac{1}{x}$

链式法则：

$$\frac{d}{dx}f(g(x)) = f'(g(x)) \cdot g'(x)$$

### 积分公式 / Integral Formulas

基本积分：

$$\int x^n dx = \frac{x^{n+1}}{n+1} + C \quad (n \neq -1)$$

$$\int \frac{1}{x} dx = \ln|x| + C$$

$$\int e^x dx = e^x + C$$

分部积分法：

$$\int u \, dv = uv - \int v \, du$$

## 线性代数 / Linear Algebra

### 矩阵运算 / Matrix Operations

矩阵乘法：设 $A$ 为 $m \times n$ 矩阵，$B$ 为 $n \times p$ 矩阵，则：

$$(AB)_{ij} = \sum_{k=1}^n a_{ik}b_{kj}$$

矩阵转置：

$$(A^T)_{ij} = A_{ji}$$

### 行列式 / Determinants

2×2 矩阵行列式：

$$\det\begin{pmatrix} a & b \\ c & d \end{pmatrix} = ad - bc$$

3×3 矩阵行列式（萨吕斯法则）：

$$\det\begin{pmatrix} a & b & c \\ d & e & f \\ g & h & i \end{pmatrix} = aei + bfg + cdh - ceg - bdi - afh$$

### 特征值与特征向量 / Eigenvalues and Eigenvectors

特征方程：

$$\det(A - \lambda I) = 0$$

其中 $\lambda$ 是特征值，满足：

$$A\mathbf{v} = \lambda\mathbf{v}$$

$\mathbf{v}$ 为对应的特征向量。

## 概率论与统计 / Probability and Statistics

### 概率基础 / Probability Basics

条件概率：

$$P(A|B) = \frac{P(A \cap B)}{P(B)}$$

贝叶斯定理：

$$P(A|B) = \frac{P(B|A)P(A)}{P(B)}$$

### 期望与方差 / Expectation and Variance

离散随机变量的期望：

$$E[X] = \sum_{i} x_i P(X = x_i)$$

方差：

$$\text{Var}(X) = E[(X - E[X])^2] = E[X^2] - (E[X])^2$$

标准差：

$$\sigma = \sqrt{\text{Var}(X)}$$

### 常见分布 / Common Distributions

**正态分布**概率密度函数：

$$f(x) = \frac{1}{\sigma\sqrt{2\pi}} e^{-\frac{(x-\mu)^2}{2\sigma^2}}$$

**泊松分布**概率质量函数：

$$P(X = k) = \frac{\lambda^k e^{-\lambda}}{k!}$$

## 数论 / Number Theory

### 欧几里得算法 / Euclidean Algorithm

最大公约数：

$$\gcd(a, b) = \gcd(b, a \bmod b)$$

### 费马小定理 / Fermat's Little Theorem

若 $p$ 是质数，$a$ 不是 $p$ 的倍数，则：

$$a^{p-1} \equiv 1 \pmod{p}$$

### 欧拉函数 / Euler's Totient Function

$$\phi(n) = n \prod_{p|n} \left(1 - \frac{1}{p}\right)$$

其中 $p$ 是 $n$ 的所有质因数。

## 组合数学 / Combinatorics

### 排列与组合 / Permutations and Combinations

排列数：

$$P(n, r) = \frac{n!}{(n-r)!}$$

组合数：

$$C(n, r) = \binom{n}{r} = \frac{n!}{r!(n-r)!}$$

### 二项式定理 / Binomial Theorem

$$(x + y)^n = \sum_{k=0}^n \binom{n}{k} x^{n-k} y^k$$

### 鸽巢原理 / Pigeonhole Principle

如果 $n+1$ 个物体放入 $n$ 个盒子，则至少有一个盒子包含两个或更多物体。

## 复数 / Complex Numbers

### 欧拉公式 / Euler's Formula

$$e^{i\theta} = \cos\theta + i\sin\theta$$

特别地，当 $\theta = \pi$ 时：

$$e^{i\pi} + 1 = 0$$

这被称为欧拉恒等式，连接了五个最重要的数学常数。

### 复数的极坐标形式 / Polar Form

$$z = r(\cos\theta + i\sin\theta) = re^{i\theta}$$

其中 $r = |z| = \sqrt{x^2 + y^2}$，$\theta = \arg(z)$
