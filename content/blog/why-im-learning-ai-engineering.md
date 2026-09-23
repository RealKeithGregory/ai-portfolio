---
title: "Why I’m Learning AI Engineering"
slug: "why-im-learning-ai-engineering"
date: "2026-09-21"
description: "What started as a question about job security has turned into a deeper interest in how AI systems are built, evaluated, and applied."
tags:
  - AI Engineering
  - AI Reliability
  - Career
related_project:
github_url:
---

Software engineers have spent the last few years debating whether AI will eventually take our jobs. I decided I’d rather learn how it works.

That decision started partly with job security. I’ve spent more than a decade working in software quality and automation, and ignoring a technology that could fundamentally change software engineering didn’t seem like a smart career strategy. But the deeper I’ve gone into AI, the less this has felt like simply protecting myself from disruption.

I’ve become genuinely interested in the technology itself.

Large language models, retrieval-augmented generation, AI agents, reinforcement learning, neural networks, and the systems being built around them have opened up an entirely different side of software engineering for me. What interests me most isn’t just that these systems can generate an answer. It’s how we build them reliably, determine when they’re wrong, and use them to solve meaningful problems.

## More to AI Than Generative Models

My first AI engineering lesson reinforced that there is much more to AI than generative models. I started with four types of analytics: descriptive, diagnostic, predictive, and prescriptive.

Descriptive analytics asks, “What happened?” It summarizes what is already present in the data, such as how many customers churned during a given month and what characteristics those customers shared. Diagnostic analytics goes a step further and asks, “Why did it happen?” For example, if senior customers churned at a higher rate than the overall customer base, diagnostic analysis would investigate the factors that may have contributed to that difference.

Predictive analytics asks, “What is likely to happen?” It uses historical patterns to estimate future or unknown outcomes, such as which current customers are most likely to churn next month. Prescriptive analytics then asks, “What should we do?” It uses predictions alongside factors such as constraints, costs, and possible interventions to recommend an action. If a model identifies 1,500 customers as likely to churn, prescriptive analytics can help determine which customers the retention team should contact and what offers might be appropriate.

Predictive AI also made AI feel less mysterious to me. It was almost like watching a magician explain how the trick works. I was intrigued by the process behind the prediction, not just the result.

I started thinking about how companies could apply predictive AI in practical ways. A financial institution, for example, might use a predictive model to identify transactions that are more likely to be fraudulent or to estimate which borrowers have a higher risk of default based on historical data.

What stood out to me most was how familiar parts of the process felt. A model is trained, it produces predictions, and those predictions are evaluated against known outcomes. That is not identical to traditional software testing, but the underlying mindset of validating results, measuring performance, and identifying failures is very familiar to me from my QA career.

## Generative and Agentic AI

Predictive AI helped demystify AI for me, but generative and agentic AI showed me how much further these systems can go.

Generative AI creates new content based on patterns learned during training. That content can include text, images, audio, video, and code. ChatGPT is a familiar example. Modern systems can also be multimodal, meaning they can work across more than one type of data, such as text and images.

Large language models, or LLMs, caught my attention because of how they generate language. Before text reaches the model, it is broken into tokens. A token may represent an entire word, part of a word, punctuation, or another small unit of text. During generation, the model repeatedly predicts a likely next token based on the context it has been given. That process continues until the response reaches a stopping condition.

A standalone LLM can generate an output, but it cannot independently call an API, query a database, or modify an external system unless the surrounding application gives it those capabilities.

That is where agentic AI becomes more interesting.

In an agentic system, a model can be given instructions, goals, tools, permission boundaries, and a workflow for completing a task. Those tools may include functions, APIs, database operations, or other capabilities exposed through application code.

I think of agents somewhat like workers on a construction site. Each worker may have a specific responsibility and a defined set of tools, but the overall system still needs coordination, boundaries, and oversight.

Giving a model access to tools makes it more useful, but it also increases the consequences of a mistake. A model-generated tool request should not automatically be trusted simply because the model produced it. The application still needs to validate inputs, enforce permissions, and restrict what actions are allowed.

This is where my QA background immediately becomes relevant. The more autonomy a system has, the more important it becomes to test its boundaries, validate its actions, and understand how it behaves when something goes wrong. Carefully defining an agent’s responsibilities and workflow can improve not only its effectiveness, but also its reliability and safety.

## Why Finance and AI Caught My Attention

As I started learning more about AI, finance quickly became one of the areas I wanted to explore further. I already had an interest in financial technology and cryptocurrency, but what really caught my attention was reading about AI agents using cryptocurrency for payments, interacting with financial data and APIs, and executing transactions through blockchain infrastructure.

Finance is also a strong fit for the way I already think as a QA engineer. Financial systems cannot simply be impressive. They need to be accurate, traceable, reliable, and carefully controlled. A model making a mistake in a casual chatbot is one thing. A model making a bad decision while interacting with financial data or executing an external action carries a considerably higher level of risk.

That is one of the areas I want to explore throughout this journey. I want to understand not only how AI systems are built, but how they can be tested, evaluated, and made reliable enough to operate in environments where mistakes matter.

## What I’ll Be Building

As I continue learning AI engineering, I have several projects planned that will let me apply these concepts in practice. For each project, I want to document more than the final result. I plan to explain what I built, how I designed it, the key decisions I made, what worked, what failed, and what I would change if I built it again.

Just as importantly, I want to document how I tested each system. That includes failure modes, reliability issues, evaluation methods, and the problems that only became visible once the application was actually running.

The first project will be an Agentic Knowledge Base Assistant, a Retrieval-Augmented Generation, or RAG, system that answers questions using custom documents. This project will give me practical experience with retrieval, context-aware generation, and applied natural language processing. I am particularly interested in testing whether the system retrieves the right information and whether its answers remain grounded in the source material.

The second project will be a Smart Personal AI Agent. This system will connect an AI model with external tools and APIs for areas such as weather, travel, and productivity. It will give me experience with agent loops, tool calling, decision-making, and the reliability challenges that appear when a model is given the ability to take actions rather than simply generate text.

The third project will be a Multi-Agent Research and Task Automation System. Specialized agents will work together to complete more complex tasks. A Planner Agent will interpret the request and determine the approach, a Research Agent will gather the necessary information, and an Executor Agent will produce results or trigger automations. I want to explore not only how multiple agents can collaborate, but whether adding more agents actually improves the system enough to justify the additional complexity.

My final project will bring these ideas together in a larger AI engineering system focused on finance. I plan to combine areas such as financial data analysis, retrieval, structured outputs, AI agents, tool use, evaluation, guardrails, and observability into one application. Because financial systems require a high degree of accuracy and control, reliability will be a major part of how I design and evaluate it.

This blog will be where I document that progression. I will share what I learn, what I build, how I test it, where the systems fail, and how my thinking changes as I gain more experience.

I am still early in the process, and there is a lot I do not know yet. That is exactly why I want to document it.

I would rather understand where AI is going than watch it happen from the sidelines.
