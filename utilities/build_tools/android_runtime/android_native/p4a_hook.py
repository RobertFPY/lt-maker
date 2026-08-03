from pathlib import Path


PROVIDER_CLASS = "org.lextalionis.android.LtDocumentsProvider"


def before_apk_build(_toolchain) -> None:
    """Insert the DocumentsProvider as an <application> child before render."""
    template = Path.cwd() / "templates" / "AndroidManifest.tmpl.xml"
    source = template.read_text(encoding="utf-8")
    if PROVIDER_CLASS in source:
        return

    provider = (Path(__file__).parent / "provider_manifest.xml").read_text(
        encoding="utf-8"
    ).strip()
    closing_tag = "</application>"
    if source.count(closing_tag) != 1:
        raise RuntimeError(
            f"Unexpected p4a manifest template structure: {template}"
        )
    source = source.replace(
        closing_tag,
        f"\n        {provider}\n    {closing_tag}",
        1,
    )
    template.write_text(source, encoding="utf-8", newline="\n")
