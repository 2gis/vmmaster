import pytest
import argparse


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Runs tests for coverage utility')
    parser.add_argument('-p', '--path', dest='path', default="tests")
    args = parser.parse_args()
    pytest.main(['-x', args.path])
