# LLM 信息源调研（国外第一手）

> 基于 [BestBlogs.dev](https://github.com/ginobefun/BestBlogs) 与 [CloudFlare AI Insight Daily](https://github.com/justlovemaki/CloudFlare-AI-Insight-Daily) 的调研，聚焦 LLM 技术、国外第一手来源、自进化学习需求。

## 筛选方法
- 排除 wechat2rss / 二次转载渠道，定位官方或作者主导的原始发布源
- 优先 LLM / RAG / Agent / Eval / Observability 相关主题
- 验证 RSS/Atom 可直接订阅；若无，标注需自建采集管道
- 结合 BestBlogs 170 个源与 CloudFlare AI Insight Daily 的实践，补充缺失的 LLM 深度来源

## A. Core LLM Labs & Vendors

| Source | Feed / Site | Format | Why It Matters |
| --- | --- | --- | --- |
| OpenAI Blog | https://openai.com/news/rss.xml | RSS | Official announcements, model updates, deployment guidance |
| Anthropic News | https://www.anthropic.com/news | HTML | Claude roadmap, safety research; requires custom fetch |
| Google DeepMind Blog | https://deepmind.com/blog/feed/basic/ | RSS | Frontier model research, agent papers |
| Google AI Blog | https://blog.google/technology/ai/rss/ | RSS | Gemini updates, infrastructure write-ups |
| Google Research | https://ai.googleblog.com/feeds/posts/default | RSS | Transformer & LLM research deep dives |
| Microsoft Research Blog | https://www.microsoft.com/en-us/research/feed/ | RSS | Phi series, Orca, long-context research |
| Azure AI Blog | https://azure.microsoft.com/en-us/blog/topics/artificial-intelligence/feed/ | RSS | Production deployment patterns for LLMs |
| AWS Machine Learning Blog | https://aws.amazon.com/blogs/machine-learning/feed/ | RSS | Bedrock usage, distributed training best practices |
| AWS Generative AI Blog | https://aws.amazon.com/blogs/generative-ai/feed/ | RSS | Reference architectures, enterprise case studies |
| IBM Research AI | https://research.ibm.com/blog/rss | RSS | Granite models, trust & safety research |
| Salesforce AI Research | https://blog.salesforceairesearch.com/rss/ | RSS | xLAM, CodeGen, alignment work |
| NVIDIA Technical Blog | https://developer.nvidia.com/blog/tag/generative-ai/feed/ | RSS | GPU optimization, inference kernels |
| Cohere Blog | https://txt.cohere.com | HTML | Command family updates, enterprise RAG; requires scraping |
| Mistral AI News | https://mistral.ai/news/ | HTML | Mixtral releases, open weights; requires scraping |
| Stability AI Blog | https://stability.ai/blog/rss.xml | RSS | Stable Diffusion, text-to-image → text best practices |
| Hugging Face Blog | https://huggingface.co/blog/feed.xml | RSS | Inference endpoints, open-source hub announcements |
| Databricks Blog | https://www.databricks.com/feed | RSS | Lakehouse + LLM tooling, data prep pipelines |
| Snowflake ML Blog | https://www.snowflake.com/blog/category/machine-learning/feed/ | RSS | Snowflake Cortex, feature engineering |
| Scale AI Blog | https://scale.com/blog/rss.xml | RSS | Data labeling, eval frameworks, synthetic data |
| OctoAI Blog | https://octoml.ai/blog/rss.xml | RSS | Inference optimization, AOT compilation for LLMs |

## B. Open Source LLM & Vector Frameworks

| Source | Feed / Site | Format | Why It Matters |
| --- | --- | --- | --- |
| LangChain Blog | https://blog.langchain.dev/rss/ | RSS | Agent patterns, LCEL updates |
| LangGraph Updates | https://blog.langchain.dev/tag/langgraph/rss/ | RSS | Workflow examples for graph orchestration |
| LlamaIndex Blog | https://www.llamaindex.ai/blog/feed | RSS | Composable RAG, indexing strategies |
| vLLM Medium | https://vllm.medium.com/feed | RSS | PagedAttention, inference performance |
| FastChat / Vicuna | https://lmsys.org/blog/index.xml | RSS | Arena evals, inference tooling |
| Qdrant Blog | https://qdrant.tech/index.xml | RSS | Vector DB best practices, hybrid search |
| Pinecone Learn | https://www.pinecone.io/learn/feed/ | RSS | Vector search tutorials, RAG guides |
| Weaviate Blog | https://weaviate.io/blog/rss.xml | RSS | Multimodal RAG, generative search |
| Milvus Blog | https://milvus.io/blog/rss/ | RSS | Distributed vector DB operations |
| Chroma Blog | https://blog.trychroma.com/feed | RSS | Embedding store updates, open-source roadmap |
| LanceDB Blog | https://blog.lancedb.com/feed | RSS | Multimodal storage, columnar vector indexing |
| Vespa Blog | https://blog.vespa.ai/feed.xml | RSS | Hybrid retrieval, production RAG |
| Haystack by deepset | https://haystack.deepset.ai/blog/rss.xml | RSS | Pipeline orchestration, retrieval plugins |
| Ray / Anyscale Blog | https://www.anyscale.com/blog/rss | RSS | Distributed fine-tuning, serve |
| Modal Blog | https://modal.com/blog/rss | RSS | Serverless inference patterns |
| Flyte Blog | https://flyte.org/blog/rss.xml | RSS | LLM pipelines, feature store integrations |
| Prefect Blog | https://www.prefect.io/blog/rss.xml | RSS | Orchestrating RAG workflows |
| Dagster Blog | https://dagster.io/blog/rss.xml | RSS | LLM ETL pipelines |
| Supabase AI | https://supabase.com/blog/tags/ai/rss.xml | RSS | Vector extension for Postgres |
| Neon Blog | https://neon.tech/blog/rss.xml | RSS | Serverless Postgres + pgvector |

## C. Research Labs & Universities

| Source | Feed / Site | Format | Why It Matters |
| --- | --- | --- | --- |
| Berkeley BAIR Blog | https://bair.berkeley.edu/blog/feed.xml | RSS | LLM alignment, agent research |
| Stanford HAI | https://hai.stanford.edu/news/rss.xml | RSS | Policy + technical work on foundation models |
| Stanford CRFM | https://crfm.stanford.edu/news.xml | RSS | Foundation model evals, HELM, Benchmarking |
| MIT CSAIL News | https://www.csail.mit.edu/rss.xml | RSS | Research breakthroughs on ML systems |
| MIT-IBM Watson AI Lab | https://mitibmwatsonailab.mit.edu/feed/ | RSS | Enterprise LLM research |
| CMU ML Blog | https://blog.ml.cmu.edu/feed/ | RSS | Carnegie Mellon ML Dept research posts |
| Allen Institute for AI | https://allenai.org/rss.xml | RSS | OLMo, AI2 research updates |
| UW NLP | https://nlp.cs.washington.edu/rss.xml | RSS | Instruction tuning research |
| NYU CDS | https://cds.nyu.edu/feed/ | RSS | Professor Yann LeCun lab updates |
| Oxford Applied AI | https://www.oxfordml.group/blog?format=rss | RSS | Probabilistic LLMs, interpretability |
| UCLA NLP | https://uclanlp.medium.com/feed | RSS | Instruction following, dataset curation |
| ETH AI Center | https://ai.ethz.ch/news-and-events/news.html/rss | RSS | Robustness & safety |
| MILA Québec | https://mila.quebec/en/news/feed/ | RSS | Generative modeling research |
| Vector Institute | https://vectorinstitute.ai/feed/ | RSS | LLM commercialization studies |
| FAIR Publications | https://ai.facebook.com/research/publications/rss | RSS | Research papers feed |
| Google Research Publications | https://research.google/blog/rss/ | RSS | Latest publications & blog posts |
| Naver AI Lab | https://naver-ai.github.io/feed.xml | RSS | HyperClova research |
| EPFL NLP Lab | https://nlp.epfl.ch/index.xml | RSS | Multilingual LLM research |
| TUM AI Lab | https://tum-ailab.github.io/feed.xml | RSS | Knowledge retrieval, robotics + LLMs |
| USC Viterbi AI | https://viterbischool.usc.edu/news/category/artificial-intelligence/feed/ | RSS | Interactive AI research |

## D. Practitioners & KOL Newsletters

| Source | Feed / Site | Format | Why It Matters |
| --- | --- | --- | --- |
| Ben's Bites | https://www.bensbites.co/feed | RSS | Daily AI builder updates |
| TLDR AI | https://kill-the-newsletter.com/feeds/zv5vv6p5u4jiwj6e1lzx.xml | RSS | High-signal daily digest |
| Import AI | https://jack-clark.net/feed/ | RSS | Jack Clark weekly deep dives |
| Latent Space | https://www.latent.space/feed | RSS | Founders building with LLMs |
| Last Week in AI | https://lastweekin.ai/feed | RSS | Weekly roundup with analysis |
| The Neuron | https://www.theneurondaily.com/feed | RSS | Investor-focused AI updates |
| Superhuman AI | https://superhuman.ai/feed | RSS | Tooling and engineering best practices |
| AI Tidbits | https://aitidbits.substack.com/feed | RSS | Concise weekly RAG updates |
| Venture in AI | https://ventureinai.substack.com/feed | RSS | Applied AI venture insights |
| One Useful Thing | https://www.oneusefulthing.org/feed | RSS | Ethan Mollick practical experiments |
| Data Science at Home | https://atasciic.substack.com/feed | RSS | LLM for data workflows |
| Prompt Engineering Daily | https://promptengineering.substack.com/feed | RSS | Prompt design patterns |
| Generative AI with Python | https://newsletter.datatonic.com/feed | RSS | Hands-on tutorials |
| Applied LLMs | https://applied-llms.com/feed | RSS | Production LLM case studies |
| AI with Vercel | https://vercel.com/blog/tags/ai/rss.xml | RSS | Edge deployment patterns |
| AI Notebooks by Hamel | https://hamel.dev/feed.xml | RSS | Experiment logs from Hamel Husain |
| Lazy Programmer | https://lazyprogrammer.me/feed/ | RSS | LLM math + coding deep dives |
| Andrej Karpathy | https://karpathy.medium.com/feed | RSS | Training from scratch series |
| Jeremy Howard / fast.ai | https://www.fast.ai/feeds/all.atom | RSS | Practical DL & LLM posts |
| Swix Blog | https://www.swyx.io/rss.xml | RSS | LLM product engineering essays |
| Chip Huyen | https://huyenchip.com/feed.xml | RSS | ML systems design |
| Eugene Yan | https://eugeneyan.com/feed.xml | RSS | Applied ML product lessons |
| Simon Willison | https://simonwillison.net/atom/everything/ | RSS | LLM tooling experiments |
| Lilian Weng | https://lilianweng.github.io/feed.xml | RSS | State-of-the-art interpretability |
| Jay Alammar | https://jalammar.github.io/feed/ | RSS | Illustrated transformer explainers |
| Sebastian Raschka | https://statsml.substack.com/feed | RSS | LLM training recipes |
| Yao Fu | https://yaofu.substack.com/feed | RSS | Research commentary |
| Matt Rickard | https://matt-rickard.com/rss | RSS | Infra + LLM product insights |
| Benedict Evans | https://www.ben-evans.com/benedictevans?format=rss | RSS | Macro trends for AI |
| Coactive AI | https://www.coactive.ai/blog/rss.xml | RSS | Multimodal AI product updates |

## E. Tooling, Eval & Observability

| Source | Feed / Site | Format | Why It Matters |
| --- | --- | --- | --- |
| Weights & Biases | https://wandb.ai/site/feed | RSS | Experiment tracking, eval frameworks |
| LangSmith | https://blog.langchain.dev/tag/langsmith/rss/ | RSS | Tracing & evaluation patterns |
| Arize AI | https://arize.com/blog/feed/ | RSS | LLM observability, eval metrics |
| WhyLabs | https://whylabs.ai/blog/rss.xml | RSS | Data monitoring for LLM pipelines |
| Humanloop | https://humanloop.com/blog/rss.xml | RSS | RLHF, prompt management |
| PromptLayer | https://promptlayer.com/blog/rss.xml | RSS | Prompt analytics |
| Ragas Blog | https://docs.ragas.io/rss.xml | RSS | LLM eval methodology |
| Evals.art | https://evals.art/feed | RSS | Benchmarks & eval visualizations |
| Helicone | https://www.helicone.ai/blog/rss.xml | RSS | LLM API observability |
| Braintrust Data | https://www.braintrustdata.com/feed | RSS | Safety guardrails |
| Truera AI | https://truera.com/blog/feed/ | RSS | Model intelligence |
| Guardrails AI | https://www.guardrailsai.com/blog?format=rss | RSS | Output validation patterns |
| LightOn AI | https://www.lighton.ai/feed | RSS | Eval research on large models |
| Scale Spellbook | https://scale.com/spellbook/blog/rss.xml | RSS | Prompt ops for enterprises |
| Aporia | https://www.aporia.com/blog/feed/ | RSS | Monitoring LLM drift |
| Digamma AI | https://digamma.ai/feed/ | RSS | Eval & QA for AI |
| PromptOps | https://promptops.ai/blog/rss.xml | RSS | LLM Ops practices |
| HoneyHive | https://honeyhive.ai/blog/rss.xml | RSS | Evaluation tooling |
| Deepchecks | https://deepchecks.com/blog/feed/ | RSS | Data validation for ML |
| Evidently AI | https://evidentlyai.com/blog/rss.xml | RSS | Monitoring dashboards |

## F. Community & Aggregated Signals

| Source | Feed / Site | Format | Why It Matters |
| --- | --- | --- | --- |
| Hacker News AI | https://hnrss.org/newest?q=ai | RSS | Community voting on AI topics |
| Hacker News LLM | https://hnrss.org/newest?q=LLM | RSS | LLM-specific threads |
| Reddit r/LocalLLaMA | https://www.reddit.com/r/LocalLLaMA/.rss | RSS | Local model experimentation |
| Reddit r/LangChain | https://www.reddit.com/r/LangChain/.rss | RSS | Framework Q&A |
| Reddit r/MachineLearning | https://www.reddit.com/r/MachineLearning/.rss | RSS | Research and paper discussions |
| Product Hunt AI | https://www.producthunt.com/feed/topic/artificial-intelligence | RSS | New AI product launches |
| Product Hunt Dev Tools | https://www.producthunt.com/feed/topic/developer-tools | RSS | Engineering tooling |
| GitHub Trending AI | https://www.daex.me/github-trending-ai.xml | RSS | Trending repos with AI tag |
| Papers with Code | https://paperswithcode.com/latest | RSS | Latest papers with code |
| arXiv cs.CL | http://export.arxiv.org/rss/cs.CL | RSS | Computational linguistics papers |
| arXiv cs.IR | http://export.arxiv.org/rss/cs.IR | RSS | Information retrieval for RAG |
| arXiv cs.LG | http://export.arxiv.org/rss/cs.LG | RSS | Core ML research |
| arXiv stat.ML | http://export.arxiv.org/rss/stat.ML | RSS | Statistical ML updates |
| arXiv cs.AI | http://export.arxiv.org/rss/cs.AI | RSS | General AI research |
| Semantic Scholar AI | https://www.semanticscholar.org/rss/topic/Artificial%20Intelligence | RSS | Curated AI papers |
| AI Alignment Forum | https://www.alignmentforum.org/feed.xml | RSS | Safety discussions |
| LessWrong AI | https://www.lesswrong.com/feed.xml?view=community&tags=lw-ai | RSS | AI risk & alignment |
| Open Source AI Radar | https://opensourceaireport.substack.com/feed | RSS | Weekly open-source highlights |
| Builder Bytes | https://builderbytes.substack.com/feed | RSS | Practical build logs |
| Terminal by Cursor | https://www.cursor.com/blog/rss.xml | RSS | AI coding workflow updates |
| Daily Papers Digest | https://dailypapers.substack.com/feed | RSS | Curated arXiv picks |
