# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('../'))
# Run the source generation step before we do the final import of item_system and skill_system
from app.engine.codegen import source_generator
source_generator.generate_all()


# -- Project information -----------------------------------------------------

project = 'lt-maker'
copyright = '2024, rainlash'
author = 'rainlash'


# -- Autodoc configuration ---------------------------------------------------
autodoc_member_order = 'bysource'  # Not alphabetical
# Not needed as long as you do UnitObject() with those parentheses on the end
# It gets rid of the init call
# autodoc_class_signature = 'separated'

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = ['myst_parser', 'sphinx_rtd_theme', 'sphinx.ext.autodoc', 'sphinx.ext.napoleon']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# ignore header level warnings
suppress_warnings = ["myst.header"]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# Allow anchors for up to h2
myst_heading_anchors = 2

html_context = {
    "display_gitlab": True, # Integrate Gitlab
    "gitlab_user": "rainlash", # Username
    "gitlab_repo": "lt-maker", # Repo name
    "gitlab_version": "master", # Version
    "conf_py_path": "/docs/", # Path in the checkout to the docs root
}

def setup(app):
    app.add_css_file("theme_overrides.css")
    from custom_directives.document_constants import DocumentConstantsList
    from custom_directives.test_directive import TestDirectiveClass
    app.add_directive('document_constants', DocumentConstantsList)
    app.add_directive('test_directive', TestDirectiveClass)