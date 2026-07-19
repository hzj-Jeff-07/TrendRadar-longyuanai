# coding=utf-8
"""双语配置文件一致性测试

config.yaml/config.en.yaml 与 timeline.yaml/timeline.en.yaml 是成对手工维护的，
本测试保证两个语言版本的 key 结构完全一致，防止只改了一边导致英文版用户行为不同。
"""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent

CONFIG_PAIRS = [
    ("config/config.yaml", "config/config.en.yaml"),
    ("config/timeline.yaml", "config/timeline.en.yaml"),
]


def structure_diffs(zh, en, path="$"):
    """递归比较两个 YAML 数据结构，返回 key 结构差异列表（值内容不比较）"""
    diffs = []
    if isinstance(zh, dict) and isinstance(en, dict):
        for key in sorted(set(zh) - set(en)):
            diffs.append(f"{path}.{key} 只存在于中文版")
        for key in sorted(set(en) - set(zh)):
            diffs.append(f"{path}.{key} 只存在于英文版")
        for key in sorted(set(zh) & set(en)):
            diffs.extend(structure_diffs(zh[key], en[key], f"{path}.{key}"))
    elif isinstance(zh, list) and isinstance(en, list):
        if len(zh) != len(en):
            diffs.append(f"{path} 列表长度不同: 中文版 {len(zh)} vs 英文版 {len(en)}")
        for i, (zh_item, en_item) in enumerate(zip(zh, en)):
            diffs.extend(structure_diffs(zh_item, en_item, f"{path}[{i}]"))
    else:
        # 数值互换（int/float）不算差异；其余类型不同视为结构漂移
        zh_is_num = isinstance(zh, (int, float)) and not isinstance(zh, bool)
        en_is_num = isinstance(en, (int, float)) and not isinstance(en, bool)
        if type(zh) is not type(en) and not (zh_is_num and en_is_num):
            diffs.append(
                f"{path} 值类型不同: 中文版 {type(zh).__name__} vs 英文版 {type(en).__name__}"
            )
    return diffs


@pytest.mark.parametrize("zh_file,en_file", CONFIG_PAIRS)
def test_bilingual_config_structure_in_sync(zh_file, en_file):
    with open(REPO_ROOT / zh_file, encoding="utf-8") as f:
        zh_data = yaml.safe_load(f)
    with open(REPO_ROOT / en_file, encoding="utf-8") as f:
        en_data = yaml.safe_load(f)

    diffs = structure_diffs(zh_data, en_data)
    assert not diffs, (
        f"{zh_file} 与 {en_file} 结构不一致（改了一边记得同步另一边）:\n"
        + "\n".join(f"  - {d}" for d in diffs)
    )


@pytest.mark.parametrize(
    "words_file",
    ["config/frequency_words.txt", "config/frequency_words.en.txt"],
)
def test_frequency_words_files_parse(words_file):
    """频率词文件（两个语言版本）都能被正常解析"""
    from trendradar.core.frequency import load_frequency_words

    groups, filter_words, global_filters = load_frequency_words(str(REPO_ROOT / words_file))
    # 默认配置至少应有一个词组或全局过滤词
    assert groups or filter_words or global_filters
