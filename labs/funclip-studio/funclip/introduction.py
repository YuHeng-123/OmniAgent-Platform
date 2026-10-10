top_md_1 = ("""
    <div class="funclip-hero">
        <div>
            <div class="funclip-kicker">本地直播录播切片工具</div>
            <h1>FunClip</h1>
            <p>上传直播录播，先识别字幕，再按文字或说话人裁剪精彩片段。</p>
        </div>
        <div class="funclip-steps">
            <span>1 上传</span>
            <span>2 识别</span>
            <span>3 裁剪</span>
        </div>
    </div>
    """)

top_md_3 = ("""访问FunASR项目与论文能够帮助您深入了解ParaClipper中所使用的语音处理相关模型：
    <div align="center">
    <div style="display:flex; gap: 0.25rem;" align="center">
        FunASR: <a href='https://github.com/alibaba-damo-academy/FunASR'><img src='https://img.shields.io/badge/Github-Code-blue'></a> 
        FunASR Paper: <a href="https://arxiv.org/abs/2305.11013"><img src="https://img.shields.io/badge/Arxiv-2305.11013-orange"></a> 
        🌟Star FunASR: <a href='https://github.com/alibaba-damo-academy/FunASR/stargazers'><img src='https://img.shields.io/github/stars/alibaba-damo-academy/FunASR.svg?style=social'></a>
    </div>
    </div>
    """)

top_md_4 = ("""我们在「LLM智能裁剪」模块中提供三种LLM调用方式，
            1. 选择阿里云百炼平台通过api调用qwen系列模型，此时需要您准备百炼平台的apikey，请访问[阿里云百炼](https://bailian.console.aliyun.com/#/home)；
            2. 选择GPT开头的模型即为调用openai官方api，此时需要您自备sk与网络环境；
            3. [gpt4free](https://github.com/xtekky/gpt4free?tab=readme-ov-file)项目也被集成进FunClip，可以通过它免费调用gpt模型；
            
            其中方式1与方式2需要在界面中传入相应的apikey        
            方式3而可能非常不稳定，返回时间可能很长或者结果获取失败，可以多多尝试或者自己准备sk使用方式1,2
            
            不要同时打开同一端口的多个界面，会导致文件上传非常缓慢或卡死，关闭其他界面即可解决
            """)
