# Survey about Efficient Inference and Small Language Models

# Survey about Efficient Inference and Small Language Models

## TL;DR
- Efficient small language models (SLMs) emerge by reducing computational overhead, demonstrated through novel architectures and quantization techniques [1].
- Research highlights the essential role of memory and inference strategies in enhancing model performance .
- Various studies propose frameworks supporting efficient local inference on edge devices .

## Background
In recent years, the focus on efficient inference in the realm of language models, especially small language models (SLMs), has gained traction. As language models expand in size and capabilities, the demand for efficiency while maintaining performance becomes paramount. Small language models promise to be cost-effective solutions equipped with efficient architectures and optimized mechanisms for runtime inference. Historically, the trade-off between model size and inference time has been a critical challenge, leading to innovations in architectures and methodologies aimed to mitigate computational loading, especially for real-world applications.

## Model Architectures for Efficiency
Recent studies demonstrate the efficacy of various architectures tailored for small language models. Notable examples include disaggregated quantization techniques  and recurrent vision transformers [2], which significantly decrease the resources required for model inference. These advancements are complemented by explorations into compositional tokenization , which enhances efficiency by structuring how input tokens are processed, thereby optimizing bandwidth usage and reducing computational overhead.

## Inference Strategies
The adoption of efficient inference strategies is crucial to enhance the performance of small language models. For instance, the use of orthogonal projection methods  helps in purifying and securing model data without extensive retraining, addressing backdoor vulnerabilities while enhancing operational efficiency. Moreover, frameworks designed for collaborative inference such as SWARM-LLM dynamically route queries between models to harness local processing capabilities effectively . This encapsulates a paradigm shift toward adaptive inference methodologies that adapt resources based on computational demand.

## Trends and open problems
The last few years have shown a substantial uptick in research tackling challenges associated with inference efficiency, especially on edge devices. Future inquiries need to address scalability issues and delve into the latency of inference models in diverse operational environments. While techniques to reduce inference costs are promising, questions linger about their applicability across various domains, especially in tasks requiring extensive reasoning or sequential processing . As efficiency draws increasing attention, therefore, balancing performance and cost will remain a pivotal area of exploration in language model research .

Key architectural principles, training paradigms, and benchmark results are further analyzed in [3].

## References
[1] Purifying Backdoored Large Vision-Language Models by Removing Hijacked Directions. arxiv. https://arxiv.org/abs/2610.09941 (2026-10-07)
[2] H2O-Danube3 Technical Report. hf-search. https://huggingface.co/papers/2407.09276 (2024-07-12)
[3] Foundations of Large Language Models. hf-daily. https://huggingface.co/papers/2501.09223 (2026-10-08)
