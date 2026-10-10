#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
# Copyright FunASR (https://github.com/alibaba-damo-academy/FunClip). All Rights Reserved.
#  MIT License  (https://opensource.org/licenses/MIT)

from http import server
import os
import logging
import argparse
import tempfile
from datetime import datetime

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ["no_proxy"] = "localhost,127.0.0.1"
os.environ["NO_PROXY"] = "localhost,127.0.0.1"

import gradio as gr
from funasr import AutoModel
from videoclipper import VideoClipper
from llm.openai_api import openai_call
from llm.qwen_api import call_qwen_model
from llm.g4f_openai_api import g4f_openai_call
from llm.twelvelabs_api import call_twelvelabs_pegasus
from utils.trans_utils import extract_timestamps
from introduction import top_md_1, top_md_3, top_md_4


DEFAULT_OUTPUT_DIR = r"D:\Codex\Projects\FunClip\output"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='argparse testing')
    parser.add_argument('--lang', '-l', type=str, default = "zh", help="language")
    parser.add_argument('--model', '-m', type=str, default="paraformer", choices=["paraformer", "fun-asr-nano", "sensevoice"], help="ASR model: paraformer, fun-asr-nano, or sensevoice")
    parser.add_argument('--share', '-s', action='store_true', help="if to establish gradio share link")
    parser.add_argument('--port', '-p', type=int, default=7860, help='port number')
    parser.add_argument('--listen', action='store_true', help="if to listen to all hosts")
    args = parser.parse_args()
    
    if args.lang == 'zh':
        if hasattr(args, 'model') and args.model == 'fun-asr-nano':
            funasr_model = AutoModel(model="FunAudioLLM/Fun-ASR-Nano-2512",
                                    trust_remote_code=True,
                                    remote_code="./model.py",
                                    vad_model="fsmn-vad",
                                    vad_kwargs={"max_single_segment_time": 30000},
                                    spk_model="cam++",
                                    hub="hf",
                                    )
        elif hasattr(args, 'model') and args.model == 'sensevoice':
            funasr_model = AutoModel(model="iic/SenseVoiceSmall",
                                    vad_model="fsmn-vad",
                                    vad_kwargs={"max_single_segment_time": 30000},
                                    spk_model="cam++",
                                    )
        else:
            funasr_model = AutoModel(model="iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
                                    vad_model="damo/speech_fsmn_vad_zh-cn-16k-common-pytorch",
                                    punc_model="damo/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
                                    spk_model="damo/speech_campplus_sv_zh-cn_16k-common",
                                    )
    else:
        funasr_model = AutoModel(model="iic/speech_paraformer_asr-en-16k-vocab4199-pytorch",
                                vad_model="damo/speech_fsmn_vad_zh-cn-16k-common-pytorch",
                                punc_model="damo/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
                                spk_model="damo/speech_campplus_sv_zh-cn_16k-common",
                                )
    audio_clipper = VideoClipper(funasr_model)
    audio_clipper.lang = args.lang
    
    server_name='127.0.0.1'
    if args.listen:
        server_name = '0.0.0.0'
        
    def save_text_to_file(content, extension, output_dir=None):
        if not content:
            return None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"result_{timestamp}.{extension}"
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            file_path = os.path.join(output_dir, filename)
        else:
            # Create a temporary file
            temp_dir = tempfile.gettempdir()
            file_path = os.path.join(temp_dir, filename)
            
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path

    def normalize_output_dir(output_dir):
        output_dir = (output_dir or "").strip()
        if not len(output_dir):
            output_dir = DEFAULT_OUTPUT_DIR
        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def save_clip_srt_file(clip_srt, clip_video_file, output_dir):
        if not clip_srt:
            return None
        output_dir = normalize_output_dir(output_dir)
        if clip_video_file:
            srt_file = os.path.splitext(clip_video_file)[0] + ".srt"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            srt_file = os.path.join(output_dir, f"clip_{timestamp}.srt")
        with open(srt_file, "w", encoding="utf-8") as fout:
            fout.write(clip_srt)
        return srt_file

    def format_clip_message(message, clip_video_file=None, srt_file=None):
        lines = []
        if message:
            lines.append(str(message))
        if clip_video_file:
            lines.append(f"视频文件：{clip_video_file}")
        if srt_file:
            lines.append(f"字幕文件：{srt_file}")
        return "\n".join(lines)

    def audio_recog(audio_input, sd_switch, hotwords, output_dir):
        return audio_clipper.recog(audio_input, sd_switch, None, hotwords, output_dir=output_dir)

    def video_recog(video_input, sd_switch, hotwords, output_dir):
        return audio_clipper.video_recog(video_input, sd_switch, hotwords, output_dir=output_dir)

    def video_clip(dest_text, video_spk_input, start_ost, end_ost, state, output_dir):
        return audio_clipper.video_clip(
            dest_text, start_ost, end_ost, state, dest_spk=video_spk_input, output_dir=output_dir
            )

    def mix_recog(video_input, audio_input, hotwords, output_dir):
        output_dir = normalize_output_dir(output_dir)
        audio_state, video_state = None, None
        if video_input is not None:
            res_text, res_srt, video_state = video_recog(
                video_input, 'No', hotwords, output_dir=output_dir)
            text_file = save_text_to_file(res_text, 'txt', output_dir)
            srt_file = save_text_to_file(res_srt, 'srt', output_dir)
            return res_text, res_srt, video_state, None, text_file, srt_file
        if audio_input is not None:
            res_text, res_srt, audio_state = audio_recog(
                audio_input, 'No', hotwords, output_dir=output_dir)
            text_file = save_text_to_file(res_text, 'txt', output_dir)
            srt_file = save_text_to_file(res_srt, 'srt', output_dir)
            return res_text, res_srt, None, audio_state, text_file, srt_file
        return "请先上传视频或音频。", "", None, None, None, None
    
    def mix_recog_speaker(video_input, audio_input, hotwords, output_dir):
        output_dir = normalize_output_dir(output_dir)
        audio_state, video_state = None, None
        if video_input is not None:
            res_text, res_srt, video_state = video_recog(
                video_input, 'Yes', hotwords, output_dir=output_dir)
            text_file = save_text_to_file(res_text, 'txt', output_dir)
            srt_file = save_text_to_file(res_srt, 'srt', output_dir)
            return res_text, res_srt, video_state, None, text_file, srt_file
        if audio_input is not None:
            res_text, res_srt, audio_state = audio_recog(
                audio_input, 'Yes', hotwords, output_dir=output_dir)
            text_file = save_text_to_file(res_text, 'txt', output_dir)
            srt_file = save_text_to_file(res_srt, 'srt', output_dir)
            return res_text, res_srt, None, audio_state, text_file, srt_file
        return "请先上传视频或音频。", "", None, None, None, None
    
    def mix_clip(dest_text, video_spk_input, start_ost, end_ost, video_state, audio_state, output_dir):
        output_dir = normalize_output_dir(output_dir)
        if video_state is not None:
            clip_video_file, message, clip_srt = audio_clipper.video_clip(
                dest_text, start_ost, end_ost, video_state, dest_spk=video_spk_input, output_dir=output_dir)
            return clip_video_file, None, message, clip_srt
        if audio_state is not None:
            (sr, res_audio), message, clip_srt = audio_clipper.clip(
                dest_text, start_ost, end_ost, audio_state, dest_spk=video_spk_input, output_dir=output_dir)
            return None, (sr, res_audio), message, clip_srt
        return None, None, "请先上传并识别视频。", ""
    
    def video_clip_addsub(dest_text, video_spk_input, start_ost, end_ost, state, output_dir, font_size, font_color):
        output_dir = normalize_output_dir(output_dir)
        if state is None:
            return None, "请先上传并识别视频。", ""
        return audio_clipper.video_clip(
            dest_text, start_ost, end_ost, state, 
            font_size=font_size, font_color=font_color, 
            add_sub=True, dest_spk=video_spk_input, output_dir=output_dir
            )

    def mix_clip_with_files(dest_text, video_spk_input, start_ost, end_ost, video_state, audio_state, output_dir):
        clip_video_file, audio_result, message, clip_srt = mix_clip(
            dest_text, video_spk_input, start_ost, end_ost, video_state, audio_state, output_dir
        )
        srt_file = save_clip_srt_file(clip_srt, clip_video_file, output_dir)
        message = format_clip_message(message, clip_video_file, srt_file)
        return clip_video_file, audio_result, message, clip_srt, clip_video_file, srt_file

    def video_clip_addsub_with_files(dest_text, video_spk_input, start_ost, end_ost, state, output_dir, font_size, font_color):
        clip_video_file, message, clip_srt = video_clip_addsub(
            dest_text, video_spk_input, start_ost, end_ost, state, output_dir, font_size, font_color
        )
        srt_file = save_clip_srt_file(clip_srt, clip_video_file, output_dir)
        message = format_clip_message(message, clip_video_file, srt_file)
        return clip_video_file, message, clip_srt, clip_video_file, srt_file
        
    def llm_inference(system_content, user_content, srt_text, model, apikey, video_input=None):
        SUPPORT_LLM_PREFIX = ['qwen', 'gpt', 'g4f', 'moonshot', 'deepseek', 'pegasus']
        if model.startswith('pegasus'):
            # TwelveLabs Pegasus reasons over the actual video (visuals + audio)
            # rather than the ASR transcript, so it needs the video source.
            if video_input is None:
                logging.error("Pegasus requires a video input; please upload a video first.")
                return "Please upload a video before running Pegasus inference."
            return call_twelvelabs_pegasus(apikey, video_input, model=model, prompt=system_content)
        if model.startswith('qwen'):
            return call_qwen_model(apikey, model, user_content+'\n'+srt_text, system_content)
        if model.startswith('gpt') or model.startswith('moonshot') or model.startswith('deepseek'):
            return openai_call(apikey, model, system_content, user_content+'\n'+srt_text)
        elif model.startswith('g4f'):
            model = "-".join(model.split('-')[1:])
            return g4f_openai_call(model, system_content, user_content+'\n'+srt_text)
        else:
            logging.error("LLM name error, only {} are supported as LLM name prefix."
                          .format(SUPPORT_LLM_PREFIX))
    
    def AI_clip(LLM_res, dest_text, video_spk_input, start_ost, end_ost, video_state, audio_state, output_dir):
        timestamp_list = extract_timestamps(LLM_res)
        output_dir = normalize_output_dir(output_dir)
        if video_state is not None:
            clip_video_file, message, clip_srt = audio_clipper.video_clip(
                dest_text, start_ost, end_ost, video_state, 
                dest_spk=video_spk_input, output_dir=output_dir, timestamp_list=timestamp_list, add_sub=False)
            return clip_video_file, None, message, clip_srt
        if audio_state is not None:
            (sr, res_audio), message, clip_srt = audio_clipper.clip(
                dest_text, start_ost, end_ost, audio_state, 
                dest_spk=video_spk_input, output_dir=output_dir, timestamp_list=timestamp_list, add_sub=False)
            return None, (sr, res_audio), message, clip_srt
        return None, None, "请先上传并识别视频。", ""
    
    def AI_clip_subti(LLM_res, dest_text, video_spk_input, start_ost, end_ost, video_state, audio_state, output_dir):
        timestamp_list = extract_timestamps(LLM_res)
        output_dir = normalize_output_dir(output_dir)
        if video_state is not None:
            clip_video_file, message, clip_srt = audio_clipper.video_clip(
                dest_text, start_ost, end_ost, video_state, 
                dest_spk=video_spk_input, output_dir=output_dir, timestamp_list=timestamp_list, add_sub=True)
            return clip_video_file, None, message, clip_srt
        if audio_state is not None:
            (sr, res_audio), message, clip_srt = audio_clipper.clip(
                dest_text, start_ost, end_ost, audio_state, 
                dest_spk=video_spk_input, output_dir=output_dir, timestamp_list=timestamp_list, add_sub=True)
            return None, (sr, res_audio), message, clip_srt
        return None, None, "请先上传并识别视频。", ""

    def AI_clip_with_files(LLM_res, dest_text, video_spk_input, start_ost, end_ost, video_state, audio_state, output_dir):
        clip_video_file, audio_result, message, clip_srt = AI_clip(
            LLM_res, dest_text, video_spk_input, start_ost, end_ost, video_state, audio_state, output_dir
        )
        srt_file = save_clip_srt_file(clip_srt, clip_video_file, output_dir)
        message = format_clip_message(message, clip_video_file, srt_file)
        return clip_video_file, audio_result, message, clip_srt, clip_video_file, srt_file
    
    def AI_clip_subti_with_files(LLM_res, dest_text, video_spk_input, start_ost, end_ost, video_state, audio_state, output_dir):
        clip_video_file, audio_result, message, clip_srt = AI_clip_subti(
            LLM_res, dest_text, video_spk_input, start_ost, end_ost, video_state, audio_state, output_dir
        )
        srt_file = save_clip_srt_file(clip_srt, clip_video_file, output_dir)
        message = format_clip_message(message, clip_video_file, srt_file)
        return clip_video_file, audio_result, message, clip_srt, clip_video_file, srt_file
    
    # gradio interface
    theme = gr.Theme.load("funclip/utils/theme.json")
    custom_css = """
    .gradio-container { max-width: 1440px !important; }
    .funclip-hero {
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 18px 22px;
        margin-bottom: 16px;
        background: #111827;
        display: flex;
        justify-content: space-between;
        gap: 18px;
        align-items: center;
    }
    .funclip-hero h1 {
        margin: 2px 0 6px;
        font-size: 34px;
        letter-spacing: 0;
    }
    .funclip-hero p {
        margin: 0;
        color: #cbd5e1;
        font-size: 16px;
    }
    .funclip-kicker {
        color: #67e8f9;
        font-size: 14px;
        font-weight: 700;
    }
    .funclip-steps {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        justify-content: flex-end;
    }
    .funclip-steps span {
        border: 1px solid #475569;
        border-radius: 8px;
        padding: 8px 12px;
        background: #1f2937;
        color: #f8fafc;
        white-space: nowrap;
    }
    textarea { line-height: 1.5 !important; }
    """
    with gr.Blocks(theme=theme, css=custom_css) as funclip_service:
        gr.Markdown(top_md_1)
        # gr.Markdown(top_md_2)
        video_state, audio_state = gr.State(), gr.State()
        local_demo_video = os.path.abspath("examples/live_screen_test.mp4")
        with gr.Row():
            with gr.Column():
                video_input = gr.Video(label="1 上传直播录播")
                with gr.Row():
                    recog_button = gr.Button("2 识别字幕", variant="primary")
                with gr.Accordion("更多输入与识别设置", open=False):
                    gr.Markdown(
                        """
                        - 音频输入：只处理音频时使用，做直播录播切片一般不用。
                        - 热词：主播名、游戏名、产品名等容易识别错的词，多个词用空格分开。
                        - 输出目录：留空也能用；建议填 `D:\\Codex\\Projects\\FunClip\\output`，方便找结果。
                        - 区分说话人：访谈、连麦、多人直播时再用，单人直播用普通识别即可。
                        """
                    )
                    audio_input = gr.Audio(label="音频（可选）")
                    hotwords_input = gr.Textbox(label="热词", placeholder="例如：主播名 游戏名 产品名")
                    output_dir = gr.Textbox(label="输出目录", value=DEFAULT_OUTPUT_DIR)
                    recog_button2 = gr.Button("识别并区分说话人")
                    if os.path.exists(local_demo_video):
                        gr.Examples(
                            [local_demo_video],
                            [video_input],
                            label="本地测试视频"
                        )
                with gr.Tab("识别文字"):
                    video_text_output = gr.Textbox(label="识别结果", lines=8)
                with gr.Tab("SRT字幕"):
                    video_srt_output = gr.Textbox(label="SRT字幕", lines=8)
                with gr.Row():
                    video_text_file = gr.File(label="下载识别文字", interactive=False)
                    video_srt_file = gr.File(label="下载SRT字幕", interactive=False)
            with gr.Column():
                with gr.Tab("手动裁剪"):
                    video_text_input = gr.Textbox(
                        label="3 要裁剪的文字",
                        placeholder="从左侧识别结果里复制一句或几句；多段用 # 连接",
                        lines=4,
                    )
                    video_spk_input = gr.Textbox(
                        label="说话人编号（可选）",
                        placeholder="使用“识别并区分说话人”后，可以填说话人编号",
                    )
                    with gr.Row():
                        clip_button = gr.Button("3 生成切片", variant="primary")
                        clip_subti_button = gr.Button("生成带字幕切片")
                    with gr.Accordion("裁剪设置与说明", open=False):
                        gr.Markdown(
                            """
                            - 复制识别结果里的原文，尽量不要改字，这样更容易切准。
                            - 多个片段用 `#` 连接，例如：`第一句话#第二句话`。
                            - 偏移量可以让切片前后多留一点时间，常用 100-300 毫秒。
                            - 想按人裁剪时，先点“识别并区分说话人”，再填写说话人编号。
                            """
                        )
                        with gr.Row():
                            video_start_ost = gr.Slider(minimum=-500, maximum=1000, value=0, step=50, label="开始前后微调（毫秒）")
                            video_end_ost = gr.Slider(minimum=-500, maximum=1000, value=100, step=50, label="结束前后微调（毫秒）")
                        with gr.Row():
                            font_size = gr.Slider(minimum=10, maximum=100, value=32, step=2, label="字幕大小")
                            font_color = gr.Radio(["black", "white", "green", "red"], label="字幕颜色", value='white')
                with gr.Tab("AI智能裁剪"):
                    with gr.Column():
                        with gr.Row():
                            llm_button =  gr.Button("生成AI建议", variant="primary")
                            llm_clip_button = gr.Button("按AI建议裁剪")
                            llm_clip_subti_button = gr.Button("按AI建议裁剪并加字幕")
                        llm_result = gr.Textbox(label="AI建议片段", lines=6)
                        with gr.Accordion("AI设置与说明", open=False):
                            gr.Markdown(
                                """
                                这里是给大模型看的设置。普通裁剪不需要填写这里。

                                - 需要先完成识别，AI 会读取左侧 SRT 字幕来挑片段。
                                - `deepseek-chat`、`qwen-plus`、`gpt` 等通常需要填写自己的 APIKEY，可能产生费用。
                                - `g4f` 不一定稳定，失败时可以换成自己的模型账号。
                                - Prompt 是给 AI 的规则，默认可以不改。
                                """
                            )
                            with gr.Row():
                                llm_model = gr.Dropdown(
                                    choices=[
                                        "deepseek-chat",
                                        "qwen-plus",
                                        "gpt-3.5-turbo", 
                                        "gpt-3.5-turbo-0125", 
                                        "gpt-4-turbo",
                                        "g4f-gpt-3.5-turbo",
                                        "pegasus1.5"],
                                    value="deepseek-chat",
                                    label="AI模型",
                                    allow_custom_value=True)
                                apikey_input = gr.Textbox(label="APIKEY", type="password")
                            prompt_head = gr.Textbox(label="系统提示词", lines=4, value=("你是一个视频srt字幕分析剪辑器，输入视频的srt字幕，"
                                    "分析其中的精彩且尽可能连续的片段并裁剪出来，输出四条以内的片段，将片段中在时间上连续的多个句子及它们的时间戳合并为一条，"
                                    "注意确保文字与时间戳的正确匹配。输出需严格按照如下格式：1. [开始时间-结束时间] 文本，注意其中的连接符是“-”"))
                            prompt_head2 = gr.Textbox(label="用户提示词", lines=2, value=("这是待裁剪的视频srt字幕："))
                video_output = gr.Video(label="裁剪结果")
                audio_output = gr.Audio(label="音频结果")
                with gr.Row():
                    latest_video_file = gr.File(label="最新视频文件", interactive=False)
                    latest_srt_file = gr.File(label="最新字幕文件", interactive=False)
                clip_message = gr.Textbox(label="处理信息", lines=3)
                srt_clipped = gr.Textbox(label="切片字幕", lines=5)            
                
        recog_button.click(mix_recog, 
                            inputs=[video_input, 
                                    audio_input, 
                                    hotwords_input, 
                                    output_dir,
                                    ], 
                            outputs=[video_text_output, video_srt_output, video_state, audio_state, video_text_file, video_srt_file])
        recog_button2.click(mix_recog_speaker, 
                            inputs=[video_input, 
                                    audio_input, 
                                    hotwords_input, 
                                    output_dir,
                                    ], 
                            outputs=[video_text_output, video_srt_output, video_state, audio_state, video_text_file, video_srt_file])
        clip_button.click(mix_clip_with_files, 
                           inputs=[video_text_input, 
                                   video_spk_input, 
                                   video_start_ost, 
                                   video_end_ost, 
                                   video_state, 
                                   audio_state, 
                                   output_dir
                                   ],
                           outputs=[video_output, audio_output, clip_message, srt_clipped, latest_video_file, latest_srt_file])
        clip_subti_button.click(video_clip_addsub_with_files, 
                           inputs=[video_text_input, 
                                   video_spk_input, 
                                   video_start_ost, 
                                   video_end_ost, 
                                   video_state, 
                                   output_dir, 
                                   font_size, 
                                   font_color,
                                   ], 
                           outputs=[video_output, clip_message, srt_clipped, latest_video_file, latest_srt_file])
        llm_button.click(llm_inference,
                         inputs=[prompt_head, prompt_head2, video_srt_output, llm_model, apikey_input, video_input],
                         outputs=[llm_result])
        llm_clip_button.click(AI_clip_with_files, 
                           inputs=[llm_result,
                                   video_text_input, 
                                   video_spk_input, 
                                   video_start_ost, 
                                   video_end_ost, 
                                   video_state, 
                                   audio_state, 
                                   output_dir,
                                   ],
                           outputs=[video_output, audio_output, clip_message, srt_clipped, latest_video_file, latest_srt_file])
        llm_clip_subti_button.click(AI_clip_subti_with_files, 
                           inputs=[llm_result,
                                   video_text_input, 
                                   video_spk_input, 
                                   video_start_ost, 
                                   video_end_ost, 
                                   video_state, 
                                   audio_state, 
                                   output_dir,
                                   ],
                           outputs=[video_output, audio_output, clip_message, srt_clipped, latest_video_file, latest_srt_file])
    
    # start gradio service in local or share
    if args.listen:
        funclip_service.launch(share=args.share, server_port=args.port, server_name=server_name, inbrowser=False)
    else:
        funclip_service.launch(share=args.share, server_port=args.port, server_name=server_name)
