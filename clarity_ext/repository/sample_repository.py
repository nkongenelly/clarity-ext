from clarity_ext.mappers.clarity_mapper import ClarityMapper


class SampleRepository(object):
    """
    During initiation of current context (i.e. at step repository at clarity-ext
    or container repository at snpseq-data) fill up a list of candidates,
    consisting of all (un-fetched) samples needed in the current context.
    Upon first request of a sample (typically within script execution), fetch
    them all in one swoop, by get_batch()
    """
    def __init__(self, session, clarity_mapper):
        self.session = session
        self.clarity_mapper = clarity_mapper
        self.candidates = list()  # not-fetched genologics sample resources
        self.samples = dict()
        self._is_fetched = False

    def add_candidate(self, sample_resource):
        self.candidates.append(sample_resource)

    def get_samples(self, sample_resources):
        if not self._is_fetched:
            self._fetch_candidates()
            self._is_fetched = True
        try:
            samples = [self.samples[s.uri] for s in sample_resources]
        except KeyError:
            raise AssertionError("All samples are not present in sample cache. "
                                 "Is SampleRepository initialized the right way?")
        return samples

    def _fetch_candidates(self):
        fetched_resources = self.session.api.get_batch(self.candidates)
        for resource in fetched_resources:
            sample = self.clarity_mapper.sample_create_object(resource)
            self.samples[resource.uri] = sample

