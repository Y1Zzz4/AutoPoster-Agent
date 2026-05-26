# AutoPoster-Agent: A Neuro-Symbolic Approach to Generative Typography

## Abstract
Traditional layout generation relies heavily on black-box diffusion models, which often fail to guarantee spatial precision and text legibility. In this paper, we present AutoPoster-Agent, a novel multi-agent framework that combines Large Language Models (LLMs) for semantic planning with rigorous Binary Space Partitioning (BSP) algorithms for pixel-perfect physical layouts.

## Introduction
The demand for automated poster generation has surged. However, achieving aesthetic balance while preventing content overlap remains a challenge. We propose a zero-shot multimodal feedback loop to simulate human design iterations.

![System Architecture](https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=800&q=80)

## Methodology
Our system consists of four main components:
1. **Unified Parser**: Extracts AST from Markdown/PDF.
2. **Hybrid Planner**: DeepSeek LLM orchestrates the semantic order.
3. **BSP Engine**: Recursively divides the canvas to prevent overlaps.
4. **Critic Agent**: Qwen-VL visually inspects the render and provides JSON feedback.

## Experimental Results
We tested AutoPoster on 100 academic abstracts. Our method achieved a 0% overlap rate compared to 35% in pure diffusion-based methods. The iterative feedback loop improved visual balance scores by 42%.

![Performance Chart](https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=800&q=80)

## Conclusion
AutoPoster demonstrates that combining deterministic algorithms with stochastic LLMs yields superior typographical results, paving the way for fully autonomous AI designers.