import unittest
from playback import Timeline, revealed_rows, consecutive_segments


class PlaybackTests(unittest.TestCase):
    def test_fills_in_text_order_including_gaps(self):
        timeline=Timeline(4)
        rows=[{'id':4,'direction':1},{'id':1,'direction':-1},{'id':3,'direction':None}]
        timeline.play()
        self.assertEqual(revealed_rows(rows,timeline.position),[])
        for index,expected in [(1,[1]),(2,[1]),(3,[1,3]),(4,[1,3,4])]:
            self.assertTrue(timeline.advance())
            self.assertEqual(timeline.position,index)
            self.assertEqual([r['id'] for r in revealed_rows(rows,timeline.position)],expected)
        self.assertFalse(timeline.playing)
        self.assertFalse(timeline.advance())

    def test_pause_resume_preserves_position(self):
        timeline=Timeline(6);timeline.play();timeline.advance();timeline.advance()
        timeline.pause();self.assertFalse(timeline.advance())
        self.assertEqual(timeline.position,2)
        timeline.play();timeline.advance();self.assertEqual(timeline.position,3)

    def test_replay_at_end_starts_empty(self):
        timeline=Timeline(1);timeline.play();timeline.advance()
        self.assertFalse(timeline.playing)
        timeline.play();self.assertEqual(timeline.position,0)

    def test_scrubbing_clamps_and_pauses(self):
        timeline=Timeline(10);timeline.play();timeline.seek(7)
        self.assertFalse(timeline.playing);self.assertEqual(timeline.position,7)
        self.assertTrue(timeline.includes(7));self.assertFalse(timeline.includes(8))
        timeline.seek(-3);self.assertEqual(timeline.position,0)
        timeline.seek(50);self.assertEqual(timeline.position,10)

    def test_new_document_resets_playback(self):
        timeline=Timeline(10);timeline.play();timeline.advance();timeline.reset(2)
        self.assertFalse(timeline.playing);self.assertIsNone(timeline.position)
        self.assertEqual(timeline.total,2)

    def test_empty_document_cannot_play(self):
        timeline=Timeline();self.assertFalse(timeline.play())
        self.assertFalse(timeline.advance())

    def test_path_does_not_bridge_missing_or_unclear_paragraphs(self):
        rows=[{'id':1,'direction':-1},{'id':2,'direction':1},
              {'id':3,'direction':None},{'id':4,'direction':0},
              {'id':6,'direction':1},{'id':7,'direction':1}]
        pairs=consecutive_segments(rows)
        self.assertEqual([(a['id'],b['id']) for a,b in pairs],[(1,2),(6,7)])
        pairs=consecutive_segments(revealed_rows(rows,6))
        self.assertEqual([(a['id'],b['id']) for a,b in pairs],[(1,2)])

    def test_reveal_does_not_mutate_model_results(self):
        rows=[{'id':2,'direction':1},{'id':1,'direction':-1}]
        self.assertEqual([r['id'] for r in revealed_rows(rows,None)],[1,2])
        self.assertEqual([r['id'] for r in rows],[2,1])

if __name__=='__main__':unittest.main()
