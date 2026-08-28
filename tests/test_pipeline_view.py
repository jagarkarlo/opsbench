import unittest

from opsbench.pipeline_view import PIPELINE_STAGES, render_pipeline_html


class PipelineViewTests(unittest.TestCase):
    def test_renders_all_pipeline_stages(self) -> None:
        html_text = render_pipeline_html()

        self.assertIn("OpsBench Pipeline", html_text)
        for stage in PIPELINE_STAGES:
            self.assertIn(f'"{stage}"', html_text)

    def test_includes_threejs_module_import(self) -> None:
        html_text = render_pipeline_html()

        self.assertIn("three@0.160.0", html_text)
        self.assertIn("requestAnimationFrame", html_text)


if __name__ == "__main__":
    unittest.main()
