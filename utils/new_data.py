from datetime import timedelta
import os
import statistics as stats
import numpy as np
from glob import glob
import matplotlib.pyplot as plt



def mgen_parse_line(line):

    def get_seconds(recv, sent):
        split_recv = [float(x) for x in recv.split(':')]
        split_sent = [float(x) for x in sent.split(':')]
        return timedelta(hours=split_recv[0]-split_sent[0], minutes=split_recv[1]-split_sent[1], seconds=split_recv[2]-split_sent[2])

    result = {}

    parts = line.split(' ')
    recvd = parts[0]
    sent = parts[7].split('>')[1]

    empty = '00:00:00'
    result['timestamp'] = int(get_seconds(recvd, empty).total_seconds() // 1)
    result['throughput'] = int(parts[8].split('>')[1]) / 125000
    result['delay'] = get_seconds(recvd, sent).total_seconds() * 1000

    return result


def mgen_parse_file(filename):
    def get_all_unique_timestamps(lst):
        timestamps = []

        for l in lst:
            if l['timestamp'] not in timestamps:
                timestamps.append(l['timestamp'])

        return timestamps

    def get_all_with_timestamp(lst, timestamp):
        return [l for l in lst if l['timestamp'] == timestamp]

    temp = []
    with open(filename, 'r') as f:
        lines = f.readlines()
        lines = lines[2:-1]
        for line in lines:
            temp.append(mgen_parse_line(line))

    with open(f'{os.path.dirname(filename)}/stats.csv', 'w') as fw:
        for timestamp in get_all_unique_timestamps(temp):
            throughput = 0
            delays = []
            for line in get_all_with_timestamp(temp, timestamp):
                throughput += line['throughput']
                delays.append(line['delay'])

            avg_delay = round(stats.mean(delays), 5)
            jitter = round(stats.variance(delays), 5) if len(delays) > 1 else 0.0

            fw.write(f'{timestamp},{throughput},{avg_delay},{jitter}\n')



def load_stats_csv_data(node_dir, x_index, y_index):
    x_list = []
    y_list = []
    node_list = []

    temp_paths = glob('{}/*/*.drc'.format(node_dir))
    print(temp_paths)
    for path in temp_paths:
        mgen_parse_file(path)

    node_dirs = glob('{}/*'.format(node_dir))
    paths = glob('{}/*/stats.csv'.format(node_dir))

    assert len(node_dirs) == len(paths) and len(paths) != 0, \
            'Is there a missing 192.168.0.X.csv file?'

    for i in range(len(paths)):
        path = paths[i]
        x_list.append(np.loadtxt(path, delimiter=',', usecols=(x_index,)))
        y_list.append(np.loadtxt(path, delimiter=',', usecols=(y_index,)))
        node_list.append(path.split('/')[-2])

    return x_list, y_list, node_list


def get_xlim(x_list):
    first = x_list[0][0]
    last = x_list[0][-1]

    for x in x_list:
        if x[0] > first:
            first = x[0]

        if x[-1] < last:
            last = x[-1]

    return first, last


def plot_stats_csv_data(node_dir, y_index, ax, label_dict):
    x_list, y_list, node_list = load_stats_csv_data(node_dir, 0, y_index)

    first, last = get_xlim(x_list)
    for x in x_list:
        for i in range(len(x)):
            x[i] = x[i] - first
    plt.xlim([0, last - first])

    labels = []
    print(node_list)
    for i in range(len(x_list)):
        # ax.plot(x_list[i], y_list[i], label=node_list[i])
        labels.append((x_list[i], y_list[i], label_dict[node_list[i]]))

    labels = sorted(labels, key=lambda tup: tup[2])
    for label in labels:
        ax.plot(label[0], label[1], label=label[2])

def plot_stats(node_dir, column='delay', ylim=5.0, show=True, title=None, label_dict=None):
    # Example react.csv row
    # timestamp, alloc, airtime, cw_prev, cw, cr
    # 1520532965.14935,0.16000,0.20536,352,356

    if column == 'throughput':
        col, name, unit = (1, 'Throughput', 'Mbps')
    elif column == 'delay':
        col, name, unit = (2, 'Delay', 'ms')
    elif column == 'jitter':
        col, name, unit = (3, 'Jitter', 'ms')
    else:
        assert False, 'Not a valid stats.csv column'

    fig, ax = plt.subplots(figsize=(6, 4), dpi=144)

    if isinstance(ylim, str):
        ylim = float(ylim)

    plot_stats_csv_data(node_dir, col, ax, label_dict)

    if ylim is not None:
        plt.ylim([0, ylim])

    if title is None:
        title = ''
    else:
        title += ': '
    title += '{} vs. Time'.format(name)

    plt.xlabel('Time')
    plt.ylabel('{} ({})'.format(name, unit))
    plt.title(title)
    plt.legend()

    save_dir = f'{node_dir}/../{column}.png'
    plt.savefig(save_dir)

    if show:
        plt.show()

    plt.close(fig)


def load_react_csv_data(node_dir, x_index, y_index):
    x_list = []
    y_list = []
    node_list = []

    node_dirs = glob('{}/*'.format(node_dir))
    paths = glob('{}/*/react.csv'.format(node_dir))

    assert len(node_dirs) == len(paths) and len(paths) != 0, \
            'Is there a missing react.csv file?'

    for i in range(len(paths)):
        path = paths[i]
        x_list.append(np.loadtxt(path, delimiter=',', usecols=(x_index,)))
        y_list.append(np.loadtxt(path, delimiter=',', usecols=(y_index,)))
        node_list.append(path.split('/')[-2])

    return x_list, y_list, node_list


def get_xlim(x_list):
    first = x_list[0][0]
    last = x_list[0][-1]

    for x in x_list:
        if x[0] > first:
            first = x[0]

        if x[-1] < last:
            last = x[-1]

    return first, last


def plot_react_csv_data(node_dir, y_index, ax, label_dict):
    x_list, y_list, node_list = load_react_csv_data(node_dir, 0, y_index)

    first, last = get_xlim(x_list)
    for x in x_list:
        for i in range(len(x)):
            x[i] = x[i] - first
    plt.xlim([0, last - first])

    labels = []
    print(node_list)
    for i in range(len(x_list)):
        # ax.plot(x_list[i], y_list[i], label=node_list[i])
        labels.append((x_list[i], y_list[i], label_dict[node_list[i]]))

    labels = sorted(labels, key=lambda tup: tup[2])
    for label in labels:
        ax.plot(label[0], label[1], label=label[2])

    to_write = []
    for i in range(len(x_list)):
        mean = stats.mean(y_list[i][5:])
        var = stats.variance(y_list[i][5:])
        dev = stats.stdev(y_list[i][10:])

        to_write.append(f'node: {node_list[i]}\n')
        to_write.append(f'mean: {mean}\n')
        to_write.append(f'variance: {var}\n')
        to_write.append(f'std dev: {dev}\n\n')

    with open(f'{node_dir}/../airtime_stats.txt', 'w') as f:
        for line in to_write:
            f.write(line)


def plot_react(node_dir, column='airtime', ylim=0.6, show=False, title=None, label_dict=None):
    # Example react.csv row
    # timestamp, alloc, airtime, cw_prev, cw, cr
    # 1520532965.14935,0.16000,0.20536,352,356

    if column == 'alloc':
        col, name, unit = (1, 'Airtime Allocation', '%')
    elif column == 'airtime':
        col, name, unit = (2, 'Airtime', '%')
    elif column == 'prev':
        col, name, unit = (3, 'Previous CW Size', '')
    elif column == 'next':
        col, name, unit = (4, 'Next CW Size', '')
    else:
        assert False, 'Not a valid react.csv column'

    fig, ax = plt.subplots(figsize=(7, 4), dpi=300)

    # if isinstance(ylim, str):
    #     ylim = float(ylim)

    plot_react_csv_data(node_dir, col, ax, label_dict)

    if title is None:
        title = ''
    else:
        title += ': '
    title += '{} vs. Time'.format(name)

    plt.xlabel('Time')
    plt.ylabel('{} ({})'.format(name, unit))
    plt.title(title)
    plt.ylim(0, ylim)
    plt.legend(ncol=4)

    save_dir = f'{node_dir}/../{column}.png'
    plt.savefig(save_dir)
    if show:
        plt.show()


def plot_line():
    directories = [
        ('/Users/danielkulenkamp/Documents/asu/research/thesis/react80211/edata/run_exps_line-mgen-exp0/000/dot/', 1.0),
        ('/Users/danielkulenkamp/Documents/asu/research/thesis/react80211/edata/run_exps_line-mgen-exp1/000/salt/', 1.0),
        ('/Users/danielkulenkamp/Documents/asu/research/thesis/react80211/edata/run_exps_line-mgen-exp2/000/salt/', 0.6),
        ('/Users/danielkulenkamp/Documents/asu/research/thesis/react80211/edata/run_exps_line-mgen-exp3/000/salt/', 0.6),
        ('/Users/danielkulenkamp/Documents/asu/research/thesis/react80211/edata/run_exps_line-mgen-exp4/000/salt/', 0.8),
        ('/Users/danielkulenkamp/Documents/asu/research/thesis/react80211/edata/run_exps_line-mgen-exp5/000/salt/', 0.6),
        ('/Users/danielkulenkamp/Documents/asu/research/thesis/react80211/edata/run_exps_line-mgen-exp6/000/salt/', 0.8),
        ('/Users/danielkulenkamp/Documents/asu/research/thesis/react80211/edata/run_exps_line-mgen-exp7/000/salt/', 0.8),
        ('/Users/danielkulenkamp/Documents/asu/research/thesis/react80211/edata/run_exps_line-mgen-exp8/000/salt/', 0.8),

    ]
    label_dict = {
        'zotacJ6.wilab2.ilabt.iminds.be': 'node 4',
        'zotacH6.wilab2.ilabt.iminds.be': 'node 3',
        'zotacF2.wilab2.ilabt.iminds.be': 'node 2',
        'zotacB3.wilab2.ilabt.iminds.be': 'node 1',
    }
    ylim_dict = {}
    for dir_tup in directories:
        print(f'Working on: {dir_tup[0]}')
        plot_stats(dir_tup[0], column='delay', ylim=2000, show=False, label_dict=label_dict)
        plot_stats(dir_tup[0], column='throughput', ylim=6, show=False, label_dict=label_dict)
        plot_stats(dir_tup[0], column='jitter', ylim=10000, show=False, label_dict=label_dict)
        plot_react(dir_tup[0], column='airtime', ylim=dir_tup[1], show=False, label_dict=label_dict)


def plot_complete():
    directories = [
        ('/Users/danielkulenkamp/Documents/asu/research/thesis/react80211/edata/run_exps_complete-mgen-exp0/003/dot/', 0.4),
        ('/Users/danielkulenkamp/Documents/asu/research/thesis/react80211/edata/run_exps_complete-mgen-exp1/003/salt/', 0.4),
        ('/Users/danielkulenkamp/Documents/asu/research/thesis/react80211/edata/run_exps_complete-mgen-exp2/003/salt/', 0.5),
        ('/Users/danielkulenkamp/Documents/asu/research/thesis/react80211/edata/run_exps_complete-mgen-exp3/003/salt/', 0.6),
        ('/Users/danielkulenkamp/Documents/asu/research/thesis/react80211/edata/run_exps_complete-mgen-exp4/000/salt/', 0.5),
        ('/Users/danielkulenkamp/Documents/asu/research/thesis/react80211/edata/run_exps_complete-mgen-exp5/000/salt/', 0.5),
        ('/Users/danielkulenkamp/Documents/asu/research/thesis/react80211/edata/run_exps_complete-mgen-exp6/000/salt/', 0.6),
        ('/Users/danielkulenkamp/Documents/asu/research/thesis/react80211/edata/run_exps_complete-mgen-exp7/000/salt/', 0.6),
        ('/Users/danielkulenkamp/Documents/asu/research/thesis/react80211/edata/run_exps_complete-mgen-exp8/000/salt/', 0.8),

    ]
    label_dict = {
        'zotacF1.wilab2.ilabt.iminds.be': 'node 1',
        'zotacF2.wilab2.ilabt.iminds.be': 'node 2',
        'zotacG2.wilab2.ilabt.iminds.be': 'node 3',
        'zotacG3.wilab2.ilabt.iminds.be': 'node 4',
    }
    for dir_tup in directories:
        print(f'Working on: {dir_tup[0]}')
        plot_stats(dir_tup[0], column='delay', ylim=2000, show=False, label_dict=label_dict)
        plot_stats(dir_tup[0], column='throughput', ylim=6, show=False, label_dict=label_dict)
        plot_stats(dir_tup[0], column='jitter', ylim=10000, show=False, label_dict=label_dict)
        plot_react(dir_tup[0], column='airtime', ylim=dir_tup[1], show=False, label_dict=label_dict)


plot_complete()
plot_line()
