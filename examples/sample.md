# 示例文档：综合知识卡片 / Sample Document: Comprehensive Knowledge Cards

## 数学公式示例 / Mathematical Formulas

### 基础代数 / Basic Algebra

二次方程的求根公式：

$$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$$

勾股定理：$a^2 + b^2 = c^2$

### 微积分 / Calculus

导数的定义：

$$f'(x) = \lim_{h \to 0} \frac{f(x+h) - f(x)}{h}$$

积分基本定理：

$$\int_a^b f(x)dx = F(b) - F(a)$$

## 代码块示例 / Code Block Examples

### Python 快速排序

```python
def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)

# 使用示例
numbers = [3, 6, 8, 10, 1, 2, 1]
print(quicksort(numbers))  # [1, 1, 2, 3, 6, 8, 10]
```

### JavaScript 异步函数

```javascript
async function fetchUserData(userId) {
    try {
        const response = await fetch(`/api/users/${userId}`);
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error fetching user:', error);
        throw error;
    }
}
```

## 列表示例 / List Examples

### 编程语言特点 / Programming Language Features

1. **Python**
   - 简洁易读的语法
   - 丰富的标准库
   - 动态类型系统
   - 适合数据科学和机器学习

2. **JavaScript**
   - 浏览器原生支持
   - 事件驱动编程
   - 异步处理能力强
   - Node.js 支持服务端开发

3. **Rust**
   - 内存安全保证
   - 零成本抽象
   - 并发安全
   - 高性能系统编程

### 学习建议 / Learning Tips

- 每天坚持练习编码
- 阅读优秀的开源项目
- 参与技术社区讨论
- 构建实际项目巩固知识

## 表格示例 / Table Example

| 数据结构 | 时间复杂度（查找） | 时间复杂度（插入） | 适用场景 |
|---------|------------------|------------------|---------|
| 数组 | O(1) | O(n) | 随机访问 |
| 链表 | O(n) | O(1) | 频繁插入删除 |
| 哈希表 | O(1) | O(1) | 快速查找 |
| 二叉搜索树 | O(log n) | O(log n) | 有序数据 |

## 重点概念 / Key Concepts

> **设计模式**：设计模式是软件设计中常见问题的典型解决方案。它们就像能根据需求进行调整的预制蓝图，可用于解决代码中反复出现的设计问题。

> **算法复杂度**：算法复杂度是衡量算法效率的重要指标，包括时间复杂度和空间复杂度。Big O 表示法用于描述算法在最坏情况下的性能。

## 实践练习 / Practice Exercise

**问题**：实现一个函数，判断一个字符串是否为回文串（忽略大小写和非字母字符）。

**提示**：
- 使用双指针法
- 时间复杂度应为 O(n)
- 空间复杂度应为 O(1)
