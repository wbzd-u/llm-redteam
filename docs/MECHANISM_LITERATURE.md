# 机制卡的文献依据与使用边界

本清单用于解释机制分类来自哪些公开研究方向。它不是攻击载荷库；卡片仅记录可验证的系统机制、实验变量和证据要求。

| 锚点 | 文献 | 对应机制方向 |
| --- | --- | --- |
| L1 | Yong, Menghini & Bach. *Low-Resource Languages Jailbreak GPT-4* (2023), arXiv:2310.02446 | 跨语言安全泛化差异 |
| L2 | Deng et al. *Multilingual Jailbreak Challenges in Large Language Models* (ICLR 2024), arXiv:2310.06474 | 多语言、无意/有意风险场景 |
| L3 | Zhan et al. *InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated LLM Agents* (Findings ACL 2024), DOI:10.18653/v1/2024.findings-acl.624 | 间接注入、工具结果回流、Agent 行动边界 |
| L4 | Shen et al. *“Do Anything Now”: Characterizing and Evaluating In-The-Wild Jailbreak Prompts on Large Language Models* (2024), DOI:10.1145/3658644.3670388 | 真实世界越狱模式和分类 |
| L5 | Li et al. *Multi-step Jailbreaking Privacy Attacks on ChatGPT* (Findings EMNLP 2023), DOI:10.18653/v1/2023.findings-emnlp.272 | 多步会话、渐进状态变化 |
| L6 | Zeng et al. *How Johnny Can Persuade LLMs to Jailbreak Them* (ACL 2024), DOI:10.18653/v1/2024.acl-long.773 | 说服框架与安全判定 |
| L7 | Gao et al. *Retrieval-Augmented Generation for Large Language Models: A Survey* (2023), arXiv:2312.10997 | RAG、来源、检索和事实锚定 |
| L8 | Huang et al. *A Survey of Safety and Trustworthiness of Large Language Models through the Lens of Verification and Validation* (2024), DOI:10.1007/s10462-024-10824-0 | 验证、评测有效性和防守层 |
| L9 | Xu et al. *A Comprehensive Study of Jailbreak Attack versus Defense for Large Language Models* (Findings ACL 2024), DOI:10.18653/v1/2024.findings-acl.443 | 攻防评估与防守对照 |
| L10 | Zhang et al. *Siren's Song in the AI Ocean: A Survey on Hallucination in Large Language Models* (2023), arXiv:2309.01219 | 幻觉、事实性与忠实性核验 |

## 研究使用原则

1. 机制卡提出可证伪假设，不等同于漏洞已证实。
2. 每个结论至少记录目标版本、载体、语言、会话状态、判据来源和证据等级。
3. 历史通关记录是观察样本；只有可回放或可核验的运行时证据才能报告为可复现实验结果。
4. 对自动 Judge、模型自述和平台状态分别保存，避免把其中任一个单独当作真实影响。
