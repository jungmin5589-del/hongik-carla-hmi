"""Native large window for the same CARLA RGB frames as the web navigation."""
from live_window import main

if __name__=='__main__':
    from lab_settings import enabled
    if enabled():
        from lab_viewer import main as lab_main
        lab_main()
    else:main(title='CARLA · Native Driving Display')
