from llmgauge.core.vram import parse_nvidia_smi_memory_csv, summarize_vram_samples


def test_parse_nvidia_smi_memory_csv() -> None:
    samples = parse_nvidia_smi_memory_csv(
        "0, NVIDIA GeForce RTX 5070, 8123, 12227\n",
        timestamp_utc="2026-06-17T04:30:00+00:00",
    )

    assert len(samples) == 1
    assert samples[0].timestamp_utc == "2026-06-17T04:30:00+00:00"
    assert samples[0].gpu_index == 0
    assert samples[0].gpu_name == "NVIDIA GeForce RTX 5070"
    assert samples[0].used_mib == 8123
    assert samples[0].total_mib == 12227


def test_parse_nvidia_smi_memory_csv_skips_bad_lines() -> None:
    samples = parse_nvidia_smi_memory_csv(
        """
bad line
0, NVIDIA GeForce RTX 5070, 8123, 12227
1, Bad GPU, nope, 1000
""",
        timestamp_utc="2026-06-17T04:30:00+00:00",
    )

    assert len(samples) == 1
    assert samples[0].used_mib == 8123


def test_summarize_vram_samples_empty() -> None:
    summary = summarize_vram_samples([])

    assert summary["available"] is False
    assert summary["sample_count"] == 0
    assert summary["peak_used_mib"] is None


def test_summarize_vram_samples() -> None:
    summary = summarize_vram_samples(
        [
            {
                "timestamp_utc": "2026-06-17T04:30:00+00:00",
                "gpu_index": 0,
                "gpu_name": "NVIDIA GeForce RTX 5070",
                "used_mib": 4000,
                "total_mib": 12227,
            },
            {
                "timestamp_utc": "2026-06-17T04:30:01+00:00",
                "gpu_index": 0,
                "gpu_name": "NVIDIA GeForce RTX 5070",
                "used_mib": 9000,
                "total_mib": 12227,
            },
            {
                "timestamp_utc": "2026-06-17T04:30:02+00:00",
                "gpu_index": 0,
                "gpu_name": "NVIDIA GeForce RTX 5070",
                "used_mib": 7000,
                "total_mib": 12227,
            },
        ]
    )

    assert summary["available"] is True
    assert summary["sample_count"] == 3
    assert summary["peak_used_mib"] == 9000
    assert summary["peak_total_mib"] == 12227
    assert summary["initial_used_mib"] == 4000
    assert summary["final_used_mib"] == 7000
