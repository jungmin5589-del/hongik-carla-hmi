"""Compatibility entry for actual CARLA pedestrian action validation."""
import argparse
from validate_city_cases import run

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--action',choices=['notice','horn','highbeam','direct','wait','none'],default='horn')
    action=parser.parse_args().action
    run('yield',{'notice':'study_horn','horn':'study_horn','highbeam':'study_highbeam','direct':'study_direct','wait':'study_wait','none':'none'}[action])
