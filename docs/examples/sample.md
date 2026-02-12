# 数学公式示例文档

本文档展示了如何在 Ankismart 中使用 LaTeX 数学公式。

## 基础数学

### 算术运算

加法：$a + b = c$

减法：$x - y = z$

乘法：$m \times n = p$ 或 $m \cdot n = p$

除法：$\frac{a}{b}$ 或 $a \div b$

### 指数和对数

平方：$x^2$

立方：$x^3$

任意次幂：$x^n$

平方根：$\sqrt{x}$

n 次方根：$\sqrt[n]{x}$

自然对数：$\ln(x)$

常用对数：$\log(x)$

指数函数：$e^x$

## 代数

### 方程

一元一次方程：$ax + b = 0$

一元二次方程：$ax^2 + bx + c = 0$

求根公式：
$$
x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}
$$

### 不等式

大于：$x > y$

小于：$x < y$

大于等于：$x \geq y$

小于等于：$x \leq y$

不等于：$x \neq y$

### 方程组

$$
\begin{cases}
x + y = 5 \\
2x - y = 1
\end{cases}
$$

解：$x = 2, y = 3$

## 微积分

### 极限

$$
\lim_{x \to 0} \frac{\sin x}{x} = 1
$$

$$
\lim_{n \to \infty} \left(1 + \frac{1}{n}\right)^n = e
$$

### 导数

导数定义：
$$
f'(x) = \lim_{h \to 0} \frac{f(x+h) - f(x)}{h}
$$

常见导数：
- $(x^n)' = nx^{n-1}$
- $(\sin x)' = \cos x$
- $(\cos x)' = -\sin x$
- $(e^x)' = e^x$
- $(\ln x)' = \frac{1}{x}$

### 积分

不定积分：$\int f(x) dx$

定积分：
$$
\int_a^b f(x) dx
$$

常见积分：
$$
\int x^n dx = \frac{x^{n+1}}{n+1} + C \quad (n \neq -1)
$$

$$
\int e^x dx = e^x + C
$$

$$
\int \frac{1}{x} dx = \ln|x| + C
$$

高斯积分：
$$
\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}
$$

## 线性代数

### 向量

向量表示：$\vec{v} = (x, y, z)$

向量模：$|\vec{v}| = \sqrt{x^2 + y^2 + z^2}$

点积：$\vec{a} \cdot \vec{b} = a_1b_1 + a_2b_2 + a_3b_3$

叉积：$\vec{a} \times \vec{b}$

### 矩阵

2×2 矩阵：
$$
A = \begin{pmatrix}
a & b \\
c & d
\end{pmatrix}
$$

3×3 矩阵：
$$
B = \begin{bmatrix}
1 & 2 & 3 \\
4 & 5 & 6 \\
7 & 8 & 9
\end{bmatrix}
$$

单位矩阵：
$$
I = \begin{pmatrix}
1 & 0 & 0 \\
0 & 1 & 0 \\
0 & 0 & 1
\end{pmatrix}
$$

矩阵乘法：$C = AB$

行列式：$\det(A)$ 或 $|A|$

逆矩阵：$A^{-1}$

转置矩阵：$A^T$

## 概率统计

### 概率

概率：$P(A)$

条件概率：$P(A|B) = \frac{P(A \cap B)}{P(B)}$

贝叶斯定理：
$$
P(A|B) = \frac{P(B|A) \cdot P(A)}{P(B)}
$$

### 统计量

均值：$\mu = \frac{1}{n}\sum_{i=1}^{n} x_i$

方差：$\sigma^2 = \frac{1}{n}\sum_{i=1}^{n} (x_i - \mu)^2$

标准差：$\sigma = \sqrt{\sigma^2}$

### 分布

正态分布：
$$
f(x) = \frac{1}{\sigma\sqrt{2\pi}} e^{-\frac{(x-\mu)^2}{2\sigma^2}}
$$

二项分布：
$$
P(X = k) = \binom{n}{k} p^k (1-p)^{n-k}
$$

泊松分布：
$$
P(X = k) = \frac{\lambda^k e^{-\lambda}}{k!}
$$

## 几何

### 平面几何

圆的方程：$(x - h)^2 + (y - k)^2 = r^2$

直线方程：$y = mx + b$

点到直线距离：
$$
d = \frac{|Ax_0 + By_0 + C|}{\sqrt{A^2 + B^2}}
$$

### 三角函数

勾股定理：$a^2 + b^2 = c^2$

正弦定理：
$$
\frac{a}{\sin A} = \frac{b}{\sin B} = \frac{c}{\sin C}
$$

余弦定理：
$$
c^2 = a^2 + b^2 - 2ab\cos C
$$

三角恒等式：
- $\sin^2 x + \cos^2 x = 1$
- $\tan x = \frac{\sin x}{\cos x}$
- $\sin(2x) = 2\sin x \cos x$
- $\cos(2x) = \cos^2 x - \sin^2 x$

欧拉公式：
$$
e^{ix} = \cos x + i\sin x
$$

欧拉恒等式：
$$
e^{i\pi} + 1 = 0
$$

## 数论

### 整除

整除：$a | b$ 表示 $a$ 整除 $b$

最大公约数：$\gcd(a, b)$

最小公倍数：$\text{lcm}(a, b)$

### 同余

同余：$a \equiv b \pmod{m}$

费马小定理：
$$
a^{p-1} \equiv 1 \pmod{p}
$$
其中 $p$ 是质数，$\gcd(a, p) = 1$

## 集合论

### 集合运算

属于：$x \in A$

不属于：$x \notin A$

子集：$A \subseteq B$

真子集：$A \subset B$

并集：$A \cup B$

交集：$A \cap B$

差集：$A \setminus B$

补集：$A^c$ 或 $\overline{A}$

空集：$\emptyset$

### 集合关系

$$
A \cup B = \{x : x \in A \text{ 或 } x \in B\}
$$

$$
A \cap B = \{x : x \in A \text{ 且 } x \in B\}
$$

德摩根定律：
$$
\overline{A \cup B} = \overline{A} \cap \overline{B}
$$

$$
\overline{A \cap B} = \overline{A} \cup \overline{B}
$$

## 求和与乘积

### 求和

有限求和：
$$
\sum_{i=1}^{n} i = \frac{n(n+1)}{2}
$$

$$
\sum_{i=1}^{n} i^2 = \frac{n(n+1)(2n+1)}{6}
$$

无限求和（几何级数）：
$$
\sum_{n=0}^{\infty} ar^n = \frac{a}{1-r} \quad (|r| < 1)
$$

### 乘积

$$
\prod_{i=1}^{n} i = n!
$$

$$
\prod_{i=1}^{n} x_i = x_1 \cdot x_2 \cdot \ldots \cdot x_n
$$

## 希腊字母

常用希腊字母：

- $\alpha$ (alpha), $\beta$ (beta), $\gamma$ (gamma), $\delta$ (delta)
- $\epsilon$ (epsilon), $\zeta$ (zeta), $\eta$ (eta), $\theta$ (theta)
- $\lambda$ (lambda), $\mu$ (mu), $\pi$ (pi), $\sigma$ (sigma)
- $\phi$ (phi), $\chi$ (chi), $\psi$ (psi), $\omega$ (omega)

大写希腊字母：

- $\Gamma$ (Gamma), $\Delta$ (Delta), $\Theta$ (Theta), $\Lambda$ (Lambda)
- $\Pi$ (Pi), $\Sigma$ (Sigma), $\Phi$ (Phi), $\Omega$ (Omega)

## 特殊符号

无穷大：$\infty$

约等于：$\approx$

正比于：$\propto$

因此：$\therefore$

因为：$\because$

对于所有：$\forall$

存在：$\exists$

属于：$\in$

不属于：$\notin$

空集：$\emptyset$

偏导数：$\frac{\partial f}{\partial x}$

梯度：$\nabla f$

积分：$\oint$, $\iint$, $\iiint$

---

## 使用提示

1. **行内公式**：使用单个 `$` 包裹，例如 `$x^2$`
2. **独立公式**：使用双 `$$` 包裹，例如 `$$\int_0^\infty e^{-x^2} dx$$`
3. **转义字符**：在 JSON 中需要双重转义，例如 `\\frac` 而不是 `\frac`
4. **预览**：在 Ankismart 预览页面可以实时查看公式渲染效果
5. **兼容性**：生成的卡片在 Anki 桌面版、AnkiWeb 和移动端都能正确显示

---

**提示**：将此文档导入 Ankismart，选择合适的生成策略（如"基础问答"或"关键术语"），即可生成包含数学公式的 Anki 卡片。
