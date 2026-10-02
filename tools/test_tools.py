"""Tests for the readers under tools/: the YAML subset, the attention-design classifier, and the recipe summary."""
import pathlib, sys, unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import facts, miniyaml, recipes  # noqa: E402


class MiniYaml(unittest.TestCase):
    def test_maps_lists_scalars_and_comments(self):
        d = miniyaml.load('''
# a comment
model:
  id: "a/b"      # trailing comment
  count: 3
  ratio: 0.5
  on: true
  off: false
  nothing: null
  base_args: []
  base_env: {}
  args:
    - "--x"
    - 'it''s'
    - plain
''')
        self.assertEqual(d["model"]["id"], "a/b")
        self.assertEqual((d["model"]["count"], d["model"]["ratio"], d["model"]["on"], d["model"]["off"], d["model"]["nothing"]), (3, 0.5, True, False, None))
        self.assertEqual((d["model"]["base_args"], d["model"]["base_env"]), ([], {}))
        self.assertEqual(d["model"]["args"], ["--x", "it's", "plain"])

    def test_a_hash_inside_quotes_is_not_a_comment(self):
        self.assertEqual(miniyaml.load('k: "a # b"\n')["k"], "a # b")

    def test_lists_of_maps_and_nested_lists(self):
        d = miniyaml.load('''
dependencies:
  - note: "first"
    command: 'uv pip install x'
  - note: "second"
features:
  tool:
    args:
      - "--a"
      - "--b"
''')
        self.assertEqual(d["dependencies"], [{"note": "first", "command": "uv pip install x"}, {"note": "second"}])
        self.assertEqual(d["features"]["tool"]["args"], ["--a", "--b"])

    def test_anchors_and_aliases_and_flow_values(self):
        d = miniyaml.load('''
a: &shared
  args:
    - "--x"
b: *shared
env: {VLLM_X: "1", Y: z}
list: [1, "two", three]
''')
        self.assertEqual(d["a"], d["b"])
        self.assertEqual(d["env"], {"VLLM_X": "1", "Y": "z"})
        self.assertEqual(d["list"], [1, "two", "three"])

    def test_block_scalars(self):
        d = miniyaml.load("note: >\n  one\n  two\nnext: 1\n")
        self.assertEqual((d["note"], d["next"]), ("one two", 1))

    def test_what_it_cannot_read_it_refuses(self):
        with self.assertRaises(ValueError):
            miniyaml.load('k: "unterminated\n')


class Attention(unittest.TestCase):
    """What a token costs in cache, by design. A design we cannot count is None, never a guess."""

    def test_standard(self):
        self.assertEqual(facts.kv_descriptor({"num_hidden_layers": 36, "num_attention_heads": 32, "num_key_value_heads": 8, "head_dim": 128}), {"full": [36, 8, 128]})

    def test_hybrid_linear_counts_only_full_attention_layers(self):
        c = {"text_config": {"num_hidden_layers": 8, "num_attention_heads": 8, "num_key_value_heads": 2, "head_dim": 256, "layer_types": ["linear_attention"] * 3 + ["full_attention"] + ["linear_attention"] * 3 + ["full_attention"]}}
        self.assertEqual(facts.kv_descriptor(c), {"full": [2, 2, 256]})

    def test_sliding_and_global_layers_have_their_own_shapes(self):
        c = {"num_hidden_layers": 6, "num_attention_heads": 8, "num_key_value_heads": 4, "head_dim": 64, "sliding_window": 512, "global_head_dim": 128, "num_global_key_value_heads": 2,
             "layer_types": ["sliding_attention"] * 5 + ["full_attention"]}
        self.assertEqual(facts.kv_descriptor(c), {"full": [1, 2, 128], "slide": [5, 4, 64, 512]})

    def test_compressed_latent_attention(self):
        self.assertEqual(facts.kv_descriptor({"num_hidden_layers": 10, "num_attention_heads": 8, "kv_lora_rank": 512, "qk_rope_head_dim": 64}), {"mla": [10, 576]})

    def test_mamba_hybrids_list_a_block_type_for_every_layer(self):
        c = {"layers_block_type": ["mamba", "moe", "attention", "mamba", "attention"], "num_key_value_heads": 2, "head_dim": 128, "num_attention_heads": 8}
        self.assertEqual(facts.kv_descriptor(c), {"full": [2, 2, 128]})

    def test_a_scheme_we_cannot_count_is_not_guessed(self):
        self.assertIsNone(facts.kv_descriptor({"num_hidden_layers": 4, "num_attention_heads": 8, "num_key_value_heads": 1, "head_dim": 512, "compress_ratios": [128, 4, 0]}))
        self.assertIsNone(facts.kv_descriptor({"num_hidden_layers": 4, "num_attention_heads": 8, "num_key_value_heads": 2, "head_dim": 64, "layer_types": ["full_attention", "something_new"]}))


class Recipes(unittest.TestCase):
    def test_a_recipe_is_summarised_to_what_a_launch_needs(self):
        doc = {"model": {"model_id": "a/b", "min_vllm_version": "0.29.0", "nightly_required": True, "install": {"pip": False},
                         "docker_image": {"nvidia": "vllm/vllm-openai:nightly"}, "base_args": ["--max-num-seqs", "256"], "base_env": {"K": "1"}},
               "dependencies": [{"note": "n", "command": "uv pip install x"}, "ignored string"]}
        recipes._INDEX.clear()
        recipes._INDEX["a/b"] = ("models/x/b.yaml", doc)
        r = recipes.for_model("A/B")
        self.assertEqual((r["minVllm"], r["nightly"], r["pip"], r["image"], r["args"], r["env"]), ("0.29.0", True, False, "vllm/vllm-openai:nightly", ["--max-num-seqs", "256"], {"K": "1"}))
        self.assertEqual(r["deps"], [{"note": "n", "command": "uv pip install x"}])
        self.assertIsNone(recipes.for_model("not/there"))
        recipes._INDEX.clear()


if __name__ == "__main__":
    unittest.main()
