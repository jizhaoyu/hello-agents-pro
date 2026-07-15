# 第十一章：Agentic-RL · 学习笔记

> 用强化学习训练智能体，让AI从经验中学习

**学习时长：** 5-6小时  
**难度：** ⭐⭐⭐⭐⭐  
**前置知识：** 第1-10章内容，机器学习基础

---

## 📚 本章概述

本章介绍Agentic-RL（智能体强化学习），这是让智能体通过与环境交互不断优化自己的技术。

### 核心内容

1. **强化学习基础** - 从RL到Agentic-RL
2. **LLM训练全景** - 预训练、SFT、RLHF、GRPO
3. **数据集与奖励函数** - GSM8K数学推理数据集
4. **SFT训练** - 监督微调，LoRA参数高效训练
5. **GRPO训练** - Group Relative Policy Optimization
6. **模型评估** - 评估指标与改进方向

---

## 11.1 从 LLM 训练到 Agentic RL

### 11.1.1 从强化学习到 Agentic RL

**经典强化学习：**

```
环境 (Environment)
    ↓ 观察状态 (State)
智能体 (Agent)
    ↓ 执行动作 (Action)
环境
    ↓ 返回奖励 (Reward)
智能体学习
```

**Agentic RL 的特点：**

传统RL中，智能体通常学习简单的动作（如游戏中的"上下左右"）。而Agentic RL中：
- 动作是**自然语言**（推理、解释、工具调用）
- 状态是**对话上下文**
- 奖励来自**任务完成度**

**类比理解：**
```
传统RL ≈ 训练小孩玩游戏
    "往左走→得分+1"
    "撞墙了→得分-1"

Agentic RL ≈ 训练学生解数学题
    "写出清晰的推理步骤→奖励+1"
    "答案正确→奖励+10"
    "推理混乱→奖励-2"
```

### 11.1.2 LLM 训练全景图

```
┌─────────────────────────────────────────────────┐
│  第1阶段: 预训练 (Pre-training)                   │
│  • 目标: 学习语言基础能力                          │
│  • 数据: 海量无标注文本 (TB级)                     │
│  • 方法: 下一个token预测                          │
│  • 结果: Base模型 (如 GPT-3-Base)                │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  第2阶段: 监督微调 (SFT - Supervised Fine-Tuning)│
│  • 目标: 学习遵循指令                             │
│  • 数据: 高质量指令-回复对 (10K-100K条)           │
│  • 方法: 监督学习                                 │
│  • 结果: SFT模型 (能回答问题，但不够优化)          │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  第3阶段: 强化学习 (RL)                           │
│  • 目标: 优化回复质量                             │
│  • 方法: RLHF / GRPO / DPO                       │
│  • 结果: 对齐人类偏好的模型 (如 GPT-4)            │
└─────────────────────────────────────────────────┘
```

**各阶段特点对比：**

| 阶段 | 训练数据量 | 计算成本 | 模型能力 |
|------|-----------|---------|---------|
| **预训练** | TB级 | 极高（数百万美元） | 语言理解，但不听话 |
| **SFT** | 10K-100K | 中等 | 能遵循指令，但质量一般 |
| **RL** | 生成式数据 | 较高 | 高质量、符合人类偏好 |

### 11.1.3 Agentic RL 的核心理念

**关键洞察：**
让LLM不仅生成"正确"的答案，还要生成"优秀"的推理过程。

**示例对比：**

```
❌ 普通回答（SFT模型）：
问：小明有3个苹果，小红给了他5个，他吃了2个，还剩几个？
答：6个。

✅ Agentic RL优化后：
问：小明有3个苹果，小红给了他5个，他吃了2个，还剩几个？
答：让我们一步步分析：
1. 小明最初有 3 个苹果
2. 小红给了他 5 个，现在有 3 + 5 = 8 个
3. 他吃了 2 个，剩余 8 - 2 = 6 个
答案：6个苹果
```

**奖励设计：**
- 答案正确：+10分
- 有清晰推理步骤：+5分
- 推理逻辑严密：+3分
- 格式规范：+2分

---

## 11.2 数据集与奖励函数

### 11.2.1 GSM8K 数学推理数据集

**GSM8K简介：**
- Grade School Math 8K（小学数学8000题）
- 由OpenAI发布
- 包含8000+个数学应用题
- 每题都有详细的推理步骤

**数据格式：**
```json
{
  "question": "珍妮的狗今年10岁。一年后，它的年龄将是珍妮兔子年龄的两倍。如果兔子现在1岁，珍妮的兔子多少岁时，狗会是兔子年龄的三倍？",
  "answer": "一年后，狗的年龄是10+1=11岁。那时兔子将是11/2=5.5岁。现在兔子1岁，所以一年后兔子将是1+1=2岁。等等，让我重新思考... [详细推理] ...答案是7年后。"
}
```

**为什么选择数学推理：**
- 有明确的正确答案（便于评估）
- 需要多步推理（考验能力）
- 可自动验证（不需要人工标注）

### 11.2.2 奖励函数设计

**基础奖励函数：**
```python
def reward_function(question, generated_answer, ground_truth):
    """计算奖励值"""
    
    # 提取最终答案
    predicted = extract_final_answer(generated_answer)
    correct = extract_final_answer(ground_truth)
    
    # 1. 答案正确性 (最重要)
    if predicted == correct:
        answer_reward = 1.0
    else:
        answer_reward = -1.0
    
    # 2. 推理质量 (次要)
    reasoning_quality = evaluate_reasoning(generated_answer)
    
    # 3. 格式规范 (辅助)
    format_score = check_format(generated_answer)
    
    # 综合奖励
    total_reward = (
        0.7 * answer_reward +       # 70%权重
        0.2 * reasoning_quality +    # 20%权重
        0.1 * format_score           # 10%权重
    )
    
    return total_reward

def evaluate_reasoning(answer):
    """评估推理质量"""
    score = 0.0
    
    # 检查是否有分步推理
    if "步骤" in answer or "Step" in answer:
        score += 0.3
    
    # 检查是否有计算过程
    if re.search(r'\d+\s*[+\-*/]\s*\d+', answer):
        score += 0.3
    
    # 检查是否有中间结果
    if "=" in answer:
        score += 0.2
    
    # 检查是否有最终总结
    if "答案" in answer or "Answer" in answer:
        score += 0.2
    
    return min(score, 1.0)
```

**进阶奖励函数（使用LLM评估）：**
```python
def llm_based_reward(question, generated_answer):
    """使用LLM作为评审员"""
    
    prompt = f"""
    评估以下数学题的回答质量：
    
    问题：{question}
    回答：{generated_answer}
    
    请从以下维度评分（0-10分）：
    1. 答案正确性
    2. 推理清晰度
    3. 步骤完整性
    4. 逻辑严密性
    
    输出JSON格式：
    {{
      "correctness": 分数,
      "clarity": 分数,
      "completeness": 分数,
      "logic": 分数
    }}
    """
    
    scores = judge_llm.generate(prompt)
    
    # 综合评分
    total = (
        scores["correctness"] * 0.5 +
        scores["clarity"] * 0.2 +
        scores["completeness"] * 0.2 +
        scores["logic"] * 0.1
    )
    
    # 归一化到[-1, 1]
    return (total / 10.0) * 2 - 1
```

---

## 11.3 SFT 训练

### 11.3.1 为什么需要 SFT

**Base模型的问题：**
```python
# Base模型（只做过预训练）
prompt = "问：2+2等于几？\n答："
output = base_model.generate(prompt)
print(output)
# 输出可能是："问：3+3等于几？\n答：..." (它只是在续写文本！)
```

**SFT后的模型：**
```python
prompt = "问：2+2等于几？\n答："
output = sft_model.generate(prompt)
print(output)
# 输出："2+2=4"（真正在回答问题！）
```

**SFT的作用：**
- 让模型理解"指令-回复"模式
- 学习特定任务的格式
- 为后续RL训练打下基础

### 11.3.2 LoRA: 参数高效微调

**全量微调 vs LoRA：**

```
传统全量微调：
┌─────────────────────┐
│  预训练模型 (7B参数)  │
│  ↓ 更新所有参数       │
│  微调模型 (7B参数)    │  → 需要大量显存和时间
└─────────────────────┘

LoRA微调：
┌─────────────────────┐
│  预训练模型 (7B参数)  │  → 冻结，不更新
│     ↓  +             │
│  LoRA层 (10M参数)    │  → 只训练这一小部分
└─────────────────────┘
```

**LoRA原理：**

不直接修改大模型权重，而是添加一个小的"适配器"：

```
原始权重矩阵 W (大矩阵，冻结)
    +
LoRA矩阵: A × B (两个小矩阵，可训练)

最终输出 = W × x + A × B × x
```

**优势：**
- 只需训练1%的参数
- 显存占用大幅降低
- 训练速度快10倍+
- 可以为不同任务训练多个LoRA

### 11.3.3 SFT 训练实战

**准备数据：**
```python
# 格式化训练数据
def format_training_data(dataset):
    formatted = []
    for item in dataset:
        formatted.append({
            "prompt": f"问题：{item['question']}\n请一步步推理并给出答案。\n",
            "completion": item['answer']
        })
    return formatted

train_data = format_training_data(gsm8k_train)
```

**配置LoRA：**
```python
from peft import LoraConfig, get_peft_model

lora_config = LoraConfig(
    r=16,                    # LoRA秩（低秩分解的维度）
    lora_alpha=32,           # 缩放因子
    target_modules=["q_proj", "v_proj"],  # 应用LoRA的层
    lora_dropout=0.1,
    bias="none",
    task_type="CAUSAL_LM"
)

model = get_peft_model(base_model, lora_config)
print(f"可训练参数: {model.num_parameters()}")
# 输出：可训练参数: 10485760 (约10M，只有全量的0.15%!)
```

**训练循环：**
```python
from transformers import Trainer, TrainingArguments

training_args = TrainingArguments(
    output_dir="./sft_output",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    learning_rate=2e-4,
    warmup_steps=100,
    logging_steps=10,
    save_steps=500,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_data,
    eval_dataset=eval_data,
)

# 开始训练
trainer.train()
```

---

## 11.4 GRPO 训练

### 11.4.1 从 PPO 到 GRPO

**PPO（Proximal Policy Optimization）：**
- OpenAI用于训练ChatGPT的算法
- 需要4个模型：Policy、Value、Reference、Reward
- 训练复杂，显存占用大

**GRPO（Group Relative Policy Optimization）：**
- DeepMind提出的简化版本
- 只需要2个模型：Policy、Reference
- 通过"组内相对比较"计算奖励

**核心思想：**
```python
# 为同一个问题生成N个答案
question = "2+3等于几？"
answers = [
    "2+3=5 ✅",           # 答案A
    "2+3=6 ❌",           # 答案B  
    "让我算算，2+3=5 ✅", # 答案C
    "不知道 ❌"           # 答案D
]

# 计算每个答案的奖励
rewards = [1.0, -1.0, 0.9, -1.0]

# GRPO：让好答案概率↑，差答案概率↓
# 关键：通过"组内对比"，不需要单独的Value模型
```

### 11.4.2 GRPO 训练实战

**实现代码：**
```python
def grpo_training_step(model, batch):
    """GRPO训练的一个步骤"""
    
    questions = batch["questions"]
    
    # 1. 对每个问题生成N个候选答案
    N = 4  # 组大小
    all_answers = []
    all_log_probs = []
    
    for question in questions:
        answers = []
        log_probs = []
        
        for _ in range(N):
            answer, log_prob = model.generate_with_log_prob(question)
            answers.append(answer)
            log_probs.append(log_prob)
        
        all_answers.append(answers)
        all_log_probs.append(log_probs)
    
    # 2. 计算每个答案的奖励
    rewards = []
    for question, answers in zip(questions, all_answers):
        answer_rewards = [
            reward_function(question, ans)
            for ans in answers
        ]
        rewards.append(answer_rewards)
    
    # 3. 组内标准化（GRPO的核心）
    normalized_rewards = []
    for group_rewards in rewards:
        mean = np.mean(group_rewards)
        std = np.std(group_rewards)
        normalized = [(r - mean) / (std + 1e-8) for r in group_rewards]
        normalized_rewards.append(normalized)
    
    # 4. 计算损失并更新
    loss = 0
    for log_probs, norm_rewards in zip(all_log_probs, normalized_rewards):
        for log_prob, reward in zip(log_probs, norm_rewards):
            # Policy Gradient: -log_prob * reward
            loss += -log_prob * reward
    
    loss.backward()
    optimizer.step()
    
    return loss.item()
```

**训练循环：**
```python
for epoch in range(num_epochs):
    for batch in dataloader:
        loss = grpo_training_step(model, batch)
        
        if step % 100 == 0:
            print(f"Epoch {epoch}, Step {step}, Loss: {loss}")
            
            # 评估模型
            accuracy = evaluate(model, eval_dataset)
            print(f"Accuracy: {accuracy}%")
```

---

## 11.5 模型评估与分析

### 11.5.1 评估指标体系

**1. 任务准确率（Task Accuracy）**
```python
def evaluate_accuracy(model, test_set):
    correct = 0
    total = len(test_set)
    
    for item in test_set:
        prediction = model.generate(item["question"])
        answer = extract_final_answer(prediction)
        
        if answer == item["ground_truth"]:
            correct += 1
    
    return correct / total
```

**2. 推理质量（Reasoning Quality）**
```python
def evaluate_reasoning(model, test_set):
    scores = []
    
    for item in test_set:
        response = model.generate(item["question"])
        
        # 使用LLM评审员评分
        score = judge_llm.evaluate(
            question=item["question"],
            answer=response,
            criteria=["清晰度", "完整性", "逻辑性"]
        )
        
        scores.append(score)
    
    return np.mean(scores)
```

**3. 对比基准**
- SFT模型 vs GRPO模型
- 不同奖励函数的效果
- 不同训练数据量的影响

### 11.5.2 错误分析

**常见错误类型：**

1. **计算错误**
```
问：3 × 7 = ?
错误回答：3 × 7 = 24
原因：基础计算能力不足
```

2. **推理跳步**
```
问：小明有5个苹果...
错误回答：所以答案是8个。(缺少中间推理)
```

3. **理解偏差**
```
问：比小明多2个是多少？
错误回答：直接输出2（理解错题意）
```

---

## 11.6 本章总结

### 核心要点

1. **Agentic-RL是LLM训练的第3阶段**
   - 预训练→SFT→RL
   - 让模型不仅正确，还要优秀

2. **SFT是RL的基础**
   - LoRA实现参数高效训练
   - 只需1%的参数量

3. **GRPO简化了RL训练**
   - 组内相对比较
   - 不需要Value模型

4. **奖励函数设计是关键**
   - 平衡正确性和推理质量
   - 可以用LLM作为评审员

### 最佳实践

- ✅ 从小数据集开始实验
- ✅ 先做好SFT再进行RL
- ✅ 精心设计奖励函数
- ✅ 持续监控训练指标
- ✅ 做充分的错误分析

---

## 💡 思考题

1. 如何为多步推理任务设计奖励函数？
2. GRPO相比PPO的优劣势是什么？
3. 如何防止RL训练中的奖励hacking？
4. 能否用RL训练智能体学习使用工具？

---

**下一章预告：** 第十二章将介绍智能体性能评估，学习如何系统地评估智能体能力。
