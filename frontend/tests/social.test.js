import test from 'node:test';
import assert from 'node:assert/strict';
import { DEFAULT_CONFIG, eventStatePayload, profileUrlWarning, socialProfilesOf } from '../src/lib/config.js';

test('profile link must match its network', () => {
  assert.equal(profileUrlWarning('instagram', 'https://www.instagram.com/gdgkrakow/'), '');
  assert.equal(profileUrlWarning('instagram', 'instagram.com/gdgkrakow'), '');
  assert.equal(profileUrlWarning('x', 'https://twitter.com/gdgkrakow'), '');
  assert.equal(profileUrlWarning('mastodon', 'https://mastodon.social/@gdg'), '');
  assert.match(profileUrlWarning('linkedin', 'https://instagram.com/gdgkrakow'), /goes to instagram\.com, not LinkedIn/);
  assert.equal(profileUrlWarning('youtube', ''), '');
});

test('old configs migrate from socialChannels', () => {
  assert.deepEqual(socialProfilesOf({ socialChannels: ['instagram'] }), [{ network: 'instagram', url: '', post: true }]);
  assert.deepEqual(socialProfilesOf({}), DEFAULT_CONFIG.socialProfiles);
});

test('state payload: links-only networks never post, unknown networks dropped', () => {
  const state = eventStatePayload({
    socialProfiles: [
      { network: 'linkedin', url: ' https://www.linkedin.com/company/gdg-krakow/ ', post: true },
      { network: 'youtube', url: 'https://www.youtube.com/@GDGKrakow', post: true },
      { network: 'x', url: '', post: false },
      { network: 'myspace', url: 'x', post: true },
    ],
  });
  assert.deepEqual(state.social_channels, ['linkedin']);
  assert.equal(state.social_profiles.length, 3);
  assert.equal(state.social_profiles[0].url, 'https://www.linkedin.com/company/gdg-krakow/');
  assert.equal(state.social_profiles[1].post, false);
  assert.equal(state.event_website, 'https://devfestkrakow.pl/');
});

test('event profile <-> config round trip', async () => {
  const { profileToConfig, configToProfile, DEFAULT_COUNTDOWN_PLAN } = await import('../src/lib/config.js');
  const profile = {
    name: 'DevFest Kraków 2027',
    date: '2027-10-09',
    website: 'https://devfestkrakow.pl/',
    registration_url: '',
    venue: 'Klaster Zabłocie 20.22',
    highlights: '2 stages',
    hashtags: ['#DevFestKrakow', '#GDGKrakow'],
    social_profiles: [{ network: 'instagram', url: 'https://instagram.com/gdgkrakow', post: true }],
    countdown: DEFAULT_COUNTDOWN_PLAN,
  };
  const cfg = profileToConfig(profile);
  assert.equal(cfg.eventHashtags, '#DevFestKrakow #GDGKrakow');
  assert.equal(cfg.countdownPlan, ''); // default sequence is not stored
  const back = configToProfile(cfg);
  assert.deepEqual(back.hashtags, profile.hashtags);
  assert.equal(back.date, profile.date);
  assert.deepEqual(back.social_profiles, profile.social_profiles);
});
