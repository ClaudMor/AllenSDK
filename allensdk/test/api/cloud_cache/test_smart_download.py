import pytest
import json
import hashlib
import pathlib
from moto import mock_s3
from .utils import create_bucket
from allensdk.api.cloud_cache.cloud_cache import S3CloudCache
from allensdk.api.cloud_cache.file_attributes import CacheFileAttributes  # noqa: E501


@mock_s3
def test_smart_file_downloading(tmpdir, example_datasets):
    """
    Test that the CloudCache is smart enough to build symlinks
    where possible
    """
    test_bucket_name = 'smart_download_bucket'
    create_bucket(test_bucket_name,
                  example_datasets)

    cache_dir = pathlib.Path(tmpdir) / 'cache'
    cache = S3CloudCache(cache_dir, test_bucket_name, 'project-x')

    # download all data files from all versions, keeping track
    # of the paths to the downloaded data files
    downloaded = {}
    for version in ('1.0.0', '2.0.0', '3.0.0'):
        downloaded[version] = {}
        cache.load_manifest(f'project-x_manifest_v{version}.json')
        for file_id in ('1', '2', '3'):
            downloaded[version][file_id] = cache.download_data(file_id)

    # check that the version 1.0.0 of all files are actual files
    for file_id in ('1', '2', '3'):
        assert downloaded['1.0.0'][file_id].is_file()
        assert not downloaded['1.0.0'][file_id].is_symlink()

    # check that v2.0.0 f1.txt is a new file
    assert downloaded['2.0.0']['1'].is_file()
    assert not downloaded['2.0.0']['1'].is_symlink()

    # check that v2.0.0 f2.txt and f3.txt are symlinks to
    # the correct v1.0.0 files
    for file_id in ('2', '3'):
        assert downloaded['2.0.0'][file_id].is_file()
        assert downloaded['2.0.0'][file_id].is_symlink()

        # check that symlink points to the correct file
        test = downloaded['2.0.0'][file_id].resolve()
        control = downloaded['1.0.0'][file_id].resolve()
        if test != control:
            test = downloaded['2.0.0'][file_id].resolve()
            control = downloaded['1.0.0'][file_id].resolve()
            raise RuntimeError(f'{test} != {control}\n'
                               'even though the first is a symlink')

        # check that the absolute paths of the files are different,
        # even though one is a symlink
        test = downloaded['2.0.0'][file_id].absolute()
        control = downloaded['1.0.0'][file_id].absolute()
        if test == control:
            test = downloaded['2.0.0'][file_id].absolute()
            control = downloaded['1.0.0'][file_id].absolute()
            raise RuntimeError(f'{test} == {control}\n'
                               'even though they should be '
                               'different absolute paths')

    # repeat the above tests for v3.0.0, f1.txt
    assert downloaded['3.0.0']['1'].is_file()
    assert downloaded['3.0.0']['1'].is_symlink()

    res3 = downloaded['3.0.0']['1'].resolve()
    res1 = downloaded['1.0.0']['1'].resolve()
    if res3 != res1:
        test = downloaded['3.0.0']['1'].resolve()
        control = downloaded['1.0.0']['1'].resolve()
        raise RuntimeError(f'{test} != {control}\n'
                           'even though the first is a symlink')

    abs3 = downloaded['3.0.0']['1'].absolute()
    abs1 = downloaded['1.0.0']['1'].absolute()
    if abs3 == abs1:
        test = downloaded['3.0.0']['1'].absolute()
        control = downloaded['1.0.0']['1'].absolute()
        raise RuntimeError(f'{test} == {control}\n'
                           'even though they should be '
                           'different absolute paths')

    # check that v3 v2.txt and f3.txt are not symlinks
    assert downloaded['3.0.0']['2'].is_file()
    assert not downloaded['3.0.0']['2'].is_symlink()
    assert downloaded['3.0.0']['3'].is_file()
    assert not downloaded['3.0.0']['3'].is_symlink()


@mock_s3
def test_on_corrupted_files(tmpdir, example_datasets):
    """
    Test that the CloudCache re-downloads files when they have been
    corrupted
    """
    bucket_name = 'corruption_bucket'
    create_bucket(bucket_name,
                  example_datasets)

    cache_dir = pathlib.Path(tmpdir) / 'cache'
    cache = S3CloudCache(cache_dir, bucket_name, 'project-x')

    version_list = ('1.0.0', '2.0.0', '3.0.0')
    file_id_list = ('1', '2', '3')

    for version in version_list:
        cache.load_manifest(f'project-x_manifest_v{version}.json')
        for file_id in file_id_list:
            cache.download_data(file_id)

    # make sure that all files exist
    for version in version_list:
        cache.load_manifest(f'project-x_manifest_v{version}.json')
        for file_id in file_id_list:
            attr = cache.data_path(file_id)
            assert attr['exists']

    hasher = hashlib.blake2b()
    hasher.update(b'4567890')
    true_hash = hasher.hexdigest()

    # Check that, when a file on disk gets corrupted,
    # all of the symlinks that point back to that file
    # get marked as `not exists`

    cache.load_manifest('project-x_manifest_v1.0.0.json')
    attr = cache.data_path('2')
    with open(attr['local_path'], 'wb') as out_file:
        out_file.write(b'xxxxxx')

    attr = cache.data_path('2')
    assert not attr['exists']

    # note that v0.2.0/f2.txt is identical to v0.1.0/f2.txt
    # in the example data set
    cache.load_manifest('project-x_manifest_v2.0.0.json')
    attr = cache.data_path('2')
    assert not attr['exists']

    # re-download one of the identical files, and verify
    # that both datasets are restored
    cache.download_data('2')
    attr = cache.data_path('2')
    assert attr['exists']
    redownloaded_path = attr['local_path']

    cache.load_manifest('project-x_manifest_v1.0.0.json')
    attr = cache.data_path('2')
    assert attr['exists']
    other_path = attr['local_path']

    hasher = hashlib.blake2b()
    with open(other_path, 'rb') as in_file:
        hasher.update(in_file.read())
    assert hasher.hexdigest() == true_hash

    # The file is downloaded to other_path because that was
    # the first path originally downloaded and stored
    # in CloudCache._downloaded_data_path

    assert other_path.resolve() == redownloaded_path.resolve()
    assert other_path.absolute() != redownloaded_path.absolute()


@mock_s3
def test_corrupted_download_manifest(tmpdir, example_datasets):
    """
    Test that CloudCache can handle the case where the
    _downloaded_data_path dict gets corrupted
    """
    bucket_name = 'manifest_corruption_bucket'
    create_bucket(bucket_name,
                  example_datasets)

    cache_dir = pathlib.Path(tmpdir) / 'cache'
    cache = S3CloudCache(cache_dir, bucket_name, 'project-x')

    version_list = ('1.0.0', '2.0.0', '3.0.0')
    file_id_list = ('1', '2', '3')

    for version in version_list:
        cache.load_manifest(f'project-x_manifest_v{version}.json')
        for file_id in file_id_list:
            cache.download_data(file_id)

    with open(cache._downloaded_data_path, 'rb') as in_file:
        src_data = json.load(in_file)

    # write a corrupted downloaded_data_path
    for k in src_data:
        src_data[k] = ''
    with open(cache._downloaded_data_path, 'w') as out_file:
        out_file.write(json.dumps(src_data, indent=2))

    hasher = hashlib.blake2b()
    hasher.update(b'4567890')
    true_hash = hasher.hexdigest()

    cache.load_manifest('project-x_manifest_v1.0.0.json')
    attr = cache.data_path('2')

    # assert below will pass; because file exists and is not yet corrupted,
    # CloudCache won't consult _downloaded_data_path
    assert attr['exists']

    # now corrupt one of the data files
    with open(attr['local_path'], 'wb') as out_file:
        out_file.write(b'xxxxx')

    # now that the file is corrupted, 'exists' is False
    attr = cache.data_path('2')
    assert not attr['exists']

    # note that v0.2.0/f2.txt is identical to v0.1.0/f2.txt
    cache.load_manifest('project-x_manifest_v2.0.0.json')
    attr = cache.data_path('2')
    assert not attr['exists']

    # re download the file
    cache.download_data('2')
    attr = cache.data_path('2')
    downloaded_path = attr['local_path']

    assert attr['exists']
    hasher = hashlib.blake2b()
    with open(attr['local_path'], 'rb') as in_file:
        hasher.update(in_file.read())
    test_hash = hasher.hexdigest()
    assert test_hash == true_hash

    # check that the v0.1.0 version of the file, which should be
    # identical to the v0.2.0 version of the file, is also
    # fixed
    cache.load_manifest('project-x_manifest_v1.0.0.json')
    attr = cache.data_path('2')
    assert attr['exists']
    assert attr['local_path'].resolve() == downloaded_path.resolve()
    assert attr['local_path'].absolute() != downloaded_path.absolute()


@mock_s3
def test_reconstruction_of_local_manifest(tmpdir):
    """
    Test that, if _downloaded_data.json gets lost, it can be reconstructed
    so that the CloudCache does not automatically download new copies of files
    """

    # define a cache class that cannot download from S3
    class DummyCache(S3CloudCache):
        def _download_file(self, file_attributes: CacheFileAttributes):
            if not self._file_exists(file_attributes):
                raise RuntimeError("Cannot download files")
            return True

    # first two versions of dataset are identical;
    # third differs
    example_data = {}
    example_data['1.0.0'] = {}
    example_data['1.0.0']['f1.txt'] = {'file_id': '1', 'data': b'abc'}
    example_data['1.0.0']['f2.txt'] = {'file_id': '2', 'data': b'def'}

    example_data['2.0.0'] = {}
    example_data['2.0.0']['f1.txt'] = {'file_id': '1', 'data': b'abc'}
    example_data['2.0.0']['f2.txt'] = {'file_id': '2', 'data': b'def'}

    example_data['3.0.0'] = {}
    example_data['3.0.0']['f1.txt'] = {'file_id': '1', 'data': b'tuv'}
    example_data['3.0.0']['f2.txt'] = {'file_id': '2', 'data': b'wxy'}

    test_bucket_name = 'cache_from_scratch_bucket'
    create_bucket(test_bucket_name,
                  example_data)

    cache_dir = pathlib.Path(tmpdir) / 'cache'

    # read in v1.0.0 data files using normal S3 cache class
    cache = S3CloudCache(cache_dir, test_bucket_name, 'project-x')
    expected_hash = {}
    cache.load_manifest(f'project-x_manifest_v1.0.0.json')
    for file_id in ('1', '2'):
        local_path = cache.download_data(file_id)
        hasher = hashlib.blake2b()
        with open(local_path, 'rb') as in_file:
            hasher.update(in_file.read())
        expected_hash[file_id] = hasher.hexdigest()

    # load the other manifests, so DummyCache can get it
    cache.load_manifest(f'project-x_manifest_v2.0.0.json')
    cache.load_manifest(f'project-x_manifest_v3.0.0.json')

    # delete the JSON file that maps local path to file hash
    lookup_path = cache._downloaded_data_path
    assert lookup_path.exists()
    lookup_path.unlink()
    assert not lookup_path.exists()

    del cache

    # Reload the data using the cache class that cannot download
    # files. Verify that paths to files with the correct hashes
    # are returned. This will mean that the local manifest mapping
    # filename to file hash was correctly reconstructed.
    dummy = DummyCache(cache_dir, test_bucket_name, 'project-x')
    dummy.load_manifest(f'project-x_manifest_v2.0.0.json')
    for file_id in ('1', '2'):
       local_path = dummy.download_data(file_id)
       hasher = hashlib.blake2b()
       with open(local_path, 'rb') as in_file:
           hasher.update(in_file.read())
       assert hasher.hexdigest() == expected_hash[file_id]

    # make sure that dummy really is unable to download by trying
    # (and failing) to get data from v3.0.0
    dummy.load_manifest(f'project-x_manifest_v3.0.0.json')
    with pytest.raises(RuntimeError) as error:
        dummy.download_data('1')