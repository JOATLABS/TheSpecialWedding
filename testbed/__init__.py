# Marker file — makes ``testbed`` an importable package so drivers can do
# ``from testbed.harness import Harness`` after inserting the repo root into
# sys.path. Namespace-package (PEP 420) resolution is unreliable when a
# similarly-named distribution lives anywhere on the user's interpreter path,
# so the explicit __init__.py is the safer contract.
