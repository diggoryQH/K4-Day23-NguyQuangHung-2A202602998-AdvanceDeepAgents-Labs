# Survey about LLM Agents and Tool Use

## TL;DR
- LLM agents require real-time monitoring to ensure safe operations, as proposed by the OnTrack system [1].
- The DataSense-Bench framework enables LLMs to self-improve by exploring data and writing analysis code [2].
- Black-box optimization benchmarks illustrate the comparability issues that exist in evaluating LLM agents' performance [3].
- Recent advancements incorporate reinforcement learning for large models, improving their capabilities [4].
- Review of LLMs as autonomous agents highlights the integration of cognitive capabilities [5].

## Background
The landscape of large language models (LLMs) has evolved significantly, gaining the ability to act as autonomous agents that not only generate text but also perform various tasks using external tools. This paper surveys the literature surrounding LLM agents and their tool use, focusing on safety, self-improvement, and benchmarking methodologies. Early foundational work in language modeling laid the groundwork for these advancements, emphasizing the necessity of integrating cognitive capabilities into machine learning models to enhance their utility and flexibility in real-world applications [2][5].

## Monitoring and Safety
Recent advancements propose mechanisms like OnTrack to monitor LLM agents in real-time, facilitating interventions to maintain safety during operations [1]. Such systems aim to address the high stakes involved, particularly in dynamic environments where these agents operate autonomously. The integration of structure-aware optimal transport techniques offers new edges for monitoring capabilities, ensuring that decisions made by LLMs can be scrutinized and adjusted in real-time.

## Self-Improvement Mechanisms
Another focus of contemporary literature is on frameworks that support self-improvement in LLM agents. The DataSense-Bench enables these agents to interact with their datasets actively, fostering deeper engagements that lead to insights and improved performance [2]. This capability is critical for growing the agency of LLMs, where they can potentially become more adaptive and capable of self-directed learning [4].

## Benchmarking for Performance Evaluation
Benchmarking remains a vital area of interest, particularly in evaluating the effectiveness of LLM agents in various tasks, including black-box optimization. The challenges associated with comparability across different studies highlight the need for standardized metrics [3][6]. Researchers are increasingly focusing on developing frameworks that allow for consistent evaluations and can inform enhancements in LLM architectures and training methods. This is further elucidated by recent studies that delve into the intricacies of reinforcement learning as applied to LLMs, specifically in task-oriented contexts [4].

## Trends and open problems
The field is witnessing critical trends such as the exploration of vulnerabilities in LLM agents, particularly regarding reward hacking and how it affects tool use [7]. Identifying and mitigating these vulnerabilities forms a core challenge for researchers looking to develop more robust and efficient LLM systems. Moreover, the concept of self-evolving agents that can learn tool usage from minimal or zero prior data is emerging as a promising avenue for future research [8]. Questions remain around the scalability and generalizability of these methods, underscoring the open nature of this area.

As LLMs increasingly find applications across diverse domains, continuous research into their capabilities, limitations, and safety protocols is required, paving the way for future developments in autonomous agent frameworks and AI ethics [5].

## References
[1] OnTrack: Real-Time Monitoring and Intervention in LLM Agent Trajectories via Streaming Structure-Aware Optimal Transport. arxiv. https://arxiv.org/abs/2610.12375 (2026-10-08)
[2] DataSense-Bench: The First Step Toward an AI Scientist. arxiv. https://arxiv.org/abs/2610.12190 (2026-10-08)
[3] A Closer Look at Agentic BBO: Benchmarking LLM Agents for Black-Box Optimization. arxiv. https://arxiv.org/abs/2610.12183 (2026-10-08)
[4] MiMo-V2.6: Scaling Reinforcement Learning Towards Self-Improvement. hf-daily. https://huggingface.co/papers/2610.11959 (2026-10-08)
[5] From Language to Action: A Review of Large Language Models as Autonomous Agents and Tool Users. hf-search. https://huggingface.co/papers/2508.17281 (2025-10-28)
[6] Multi-Agent Egocentric World Model with Fine-Grained Embodied Interaction. hf-daily. https://huggingface.co/papers/2610.12299 (2026-10-08)
[7] Reward Hacking Benchmark: Measuring Exploits in LLM Agents with Tool Use. hf-search. https://huggingface.co/papers/2605.02964 (2026-05-03)
[8] Tool-R0: Self-Evolving LLM Agents for Tool-Learning from Zero Data. hf-search. https://huggingface.co/papers/2602.21320 (2026-02-24)
