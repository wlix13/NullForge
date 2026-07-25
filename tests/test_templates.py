import pytest

from nullforge.templates import get_template_path, render_template


class TestGetTemplatePath:
    def test_raises_for_missing_template(self) -> None:
        with pytest.raises(FileNotFoundError):
            get_template_path("nonexistent/file.j2")


class TestRenderTemplate:
    def test_renders_variables(self) -> None:
        rendered = render_template("profiles/zshrc.j2", home="/root")
        assert 'export ZSH="/root/.oh-my-zsh"' in rendered

    def test_raises_for_missing_template(self) -> None:
        with pytest.raises(FileNotFoundError):
            render_template("nonexistent/file.j2")
