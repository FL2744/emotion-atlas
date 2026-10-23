"""Offline native bundle smoke test, explicitly invoked by release tooling."""
import json


def run_smoke_test(app_class, report_path):
    app = app_class()
    try:
        app.set_source('First paragraph.\n\nSecond paragraph.\n\nThird paragraph.', 'Synthetic release smoke test')
        app.results = {i: {'id': i, 'intensity': .2*i, 'valence': (i-2)*.6,
            'direction': -.8 if i==1 else .3*i, 'direction_status': 'inward' if i==1 else 'outward',
            'tone': 'negative' if i==1 else 'positive', 'uncertainty': 'low', 'summary': 'Synthetic fixture; not model inference.',
            'uncertainty_note': '', 'emotions': []} for i in (1,2,3)}
        app.refresh();app.update_idletasks()
        assert len(app.plot.points)==3
        assert app.app_icon.width()>0
        app.toggle_expanded_plot();app.update_idletasks()
        assert len(app.expanded_plot.points)==3
        for mode in ['PCA 2D','PCA 3D','Emotion axes']:
            app.plot_mode.set(mode);app.change_plot_mode();app.update_idletasks()
            assert len(app.plot.points)==3
            assert app.expanded_plot.mode==mode
        app.toggle_playback();app.playback_tick();app.pause_playback()
        assert app.timeline.position==1
        assert len(app.plot.points)==1 and len(app.expanded_plot.points)==1
        app.close_expanded_plot()
        assert app.expanded_window is None
        assert not hasattr(app,'book_btn')
        app.dirty=False
        report_path.write_text(json.dumps({'version':'0.3','status':'passed','checks':[
            'native Tk startup','icon','retro controls','paragraph plot','expanded plot synchronization',
            'PCA 2D and 3D','playback from saved-style data','restore plot']},indent=2))
    finally:
        app.pause_playback();app.destroy()
