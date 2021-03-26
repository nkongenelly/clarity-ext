import os


def read_binary_file(path):
    with open(path, 'rb') as f:
        contents = f.read()
    return contents


def get_directory(sub_dir):
    this_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(this_dir, sub_dir)


def get_same_without_qc_flags():
    ddir = get_directory('same_without_qc_flags')
    path1 = os.path.join(ddir, 'artifact1.xml')
    path2 = os.path.join(ddir, 'artifact2.xml')
    return read_binary_file(path1), read_binary_file(path2)


def get_same_but_in_different_order():
    ddir = get_directory('same_with_different_order')
    path1 = os.path.join(ddir, 'artifact1.xml')
    path2 = os.path.join(ddir, 'artifact2.xml')
    return read_binary_file(path1), read_binary_file(path2)


def get_same_pools_with_different_order():
    ddir = get_directory('same_pools_with_different_order')
    path1 = os.path.join(ddir, 'artifact1.xml')
    path2 = os.path.join(ddir, 'artifact2.xml')
    return read_binary_file(path1), read_binary_file(path2)


def get_differeing_qc_flags():
    ddir = get_directory('different_qc_flag')
    path1 = os.path.join(ddir, 'artifact1.xml')
    path2 = os.path.join(ddir, 'artifact2.xml')
    return read_binary_file(path1), read_binary_file(path2)
